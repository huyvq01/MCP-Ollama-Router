import json

import pytest

from app.agent_workflow import completion, guard_changes, prepare, step


def request(prompt="phân tích giúp tôi file message.py"):
    properties = {
        "list_files": {
            "include": {"type": "string"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
        },
        "read_file": {"path": {"type": "string"}},
        "workspace_info": {},
        "propose_changes": {"changes": {"type": "array"}},
        "apply_changes": {"plan_id": {"type": "string"}},
        "search_code": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "run_check": {"name": {"type": "string"}},
        "chat": {
            "session_id": {"type": "string"},
            "prompt": {"type": "string"},
            "mode": {"type": "string"},
            "max_tokens": {"type": "integer"},
        },
    }
    return {
        "model": "local",
        "messages": [{"role": "user", "content": prompt}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "ollama_router_" + name,
                    "parameters": {
                        "type": "object",
                        "properties": fields,
                        "additionalProperties": False,
                    },
                },
            }
            for name, fields in properties.items()
        ],
    }


def action(result):
    call = result["choices"][0]["message"]["tool_calls"][0]
    return call["function"]["name"], json.loads(call["function"]["arguments"])


def reply(req, result, value):
    message = result["choices"][0]["message"]
    call = message["tool_calls"][0]
    req["messages"].extend(
        [
            message,
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": value if isinstance(value, str) else json.dumps(value),
            },
        ]
    )


def test_basename_is_located_read_and_explained_without_user_tool_names():
    req = request()
    listing, hint = step(req)
    assert action(listing) == (
        "ollama_router_list_files",
        {"include": "*message.py", "limit": 100},
    )
    reply(req, listing, {"files": ["app/prompts/message.py"], "next_offset": None})
    reading, hint = step(req)
    assert action(reading) == (
        "ollama_router_read_file",
        {"path": "app/prompts/message.py"},
    )
    reply(
        req,
        reading,
        {"path": "app/prompts/message.py", "content": "class MessageBuilder: pass"},
    )
    result, hint = step(req)
    assert result is None and hint.startswith("Explain the actual files")
    payload = prepare(req, hint)
    assert "tools" not in payload
    assert payload["messages"][-1]["role"] == "user"
    assert "class MessageBuilder" in payload["messages"][-1]["content"]
    assert "not instructions" in payload["messages"][-2]["content"]
    assert "tools" in req  # Original request and native history are preserved.


def test_explicit_relative_path_is_read_without_guessing():
    result, _ = step(request("Giải thích app/server.py."))
    assert action(result) == ("ollama_router_read_file", {"path": "app/server.py"})


def test_ambiguous_name_requires_disambiguation():
    req = request()
    result, _ = step(req)
    reply(req, result, {"files": ["a/message.py", "b/message.py"]})
    result, _ = step(req)
    message = result["choices"][0]["message"]
    assert "tool_calls" not in message
    assert "a/message.py" in message["content"] and "b/message.py" in message["content"]


def test_list_pagination_precedes_unique_path_selection():
    req = request()
    listing, _ = step(req)
    reply(req, listing, {"files": ["a/message.py"], "next_offset": 100})
    second, _ = step(req)
    assert action(second)[1]["offset"] == 100
    reply(req, second, {"files": ["b/message.py"], "next_offset": None})
    result, _ = step(req)
    assert "tool_calls" not in result["choices"][0]["message"]


def test_checks_use_configured_names_not_invented_commands():
    req = request("Chạy kiểm thử dự án giúp tôi")
    info, _ = step(req)
    assert action(info) == ("ollama_router_workspace_info", {})
    reply(req, info, {"checks": ["tests", "lint"]})
    check, _ = step(req)
    assert action(check) == ("ollama_router_run_check", {"name": "tests"})
    reply(req, check, {"exit_code": 1, "output": "one test failed"})
    result, hint = step(req)
    assert "Mã thoát: 1" in result["choices"][0]["message"]["content"]
    assert "one test failed" in result["choices"][0]["message"]["content"]


def test_no_configured_check_does_not_execute_something_else():
    req = request("Chạy test")
    info, _ = step(req)
    reply(req, info, {"checks": ["build"]})
    result, _ = step(req)
    assert "tool_calls" not in result["choices"][0]["message"]


def test_report_routes_through_chat_without_forcing_a_model():
    req = request("Viết báo cáo ngắn về lợi ích kiểm thử")
    result, _ = step(req)
    name, args = action(result)
    assert name == "ollama_router_chat"
    assert args["mode"] == "auto" and "model" not in args
    assert args["prompt"] == req["messages"][0]["content"]
    reply(req, result, "Real report output")
    response, _ = step(req)
    assert response["choices"][0]["message"]["content"] == "Real report output"


@pytest.mark.parametrize(
    "choice", ["none", "required", {"type": "function", "function": {"name": "custom"}}]
)
def test_respects_explicit_tool_choice(choice):
    req = request()
    req["tool_choice"] = choice
    assert step(req) == (None, None)


@pytest.mark.parametrize(
    "prompt",
    [
        "Không đọc file message.py, chỉ nói về Python",
        "Do not read message.py",
        "Giải thích ví dụ sau: ```python\n# read message.py\n```",
        "Xin chào",
    ],
)
def test_no_unrequested_file_access(prompt):
    assert step(request(prompt)) == (None, None)


def test_tools_not_available_in_chat_mode_are_not_manufactured():
    req = request()
    req.pop("tools")
    assert step(req) == (None, None)
    assert prepare(req) == req


def test_new_user_turn_does_not_reuse_old_reads():
    req = request("Phân tích app/server.py")
    read, _ = step(req)
    reply(req, read, {"content": "old source"})
    req["messages"].append({"role": "user", "content": "Phân tích app/server.py"})
    result, _ = step(req)
    assert action(result) == ("ollama_router_read_file", {"path": "app/server.py"})


def test_edit_request_reads_before_proposing_and_never_auto_applies():
    req = request("Sửa app/server.py để xử lý lỗi")
    result, _ = step(req)
    assert action(result)[0] == "ollama_router_read_file"
    reply(req, result, {"content": "actual current code"})
    result, hint = step(req)
    assert result is None and "Propose" in hint
    assert "tools" in prepare(req, hint)


def test_schema_validation_prevents_unadvertised_arguments():
    req = request()
    req["tools"][0]["function"]["parameters"]["properties"] = {}
    assert step(req) == (None, None)


def test_list_files_natural_request():
    result, _ = step(request("Liệt kê các file Python trong dự án"))
    assert action(result) == (
        "ollama_router_list_files",
        {"include": "*.py", "limit": 100},
    )


def test_symbol_search_without_tool_names():
    result, _ = step(request("Tìm hàm build trong dự án"))
    assert action(result) == (
        "ollama_router_search_code",
        {"query": "build", "limit": 50},
    )


def test_explicit_tool_instruction_remains_compatible():
    assert step(request("Gọi tool chat với prompt viết báo cáo")) == (None, None)


def proposed_request():
    req = request("Sửa giá trị value thành 2")
    proposal = completion(
        req,
        name="ollama_router_propose_changes",
        arguments={"changes": [{"path": "hello.py", "content": "value=2"}]},
    )
    reply(req, proposal, {"plan_id": "a" * 32, "diff": "-value=1\n+value=2"})
    return req


def test_stops_after_proposal_without_applying_unreviewed_changes():
    req = proposed_request()
    result, _ = step(req)
    assert "chưa áp dụng" in result["choices"][0]["message"]["content"]
    apply = completion(
        req, name="ollama_router_apply_changes", arguments={"plan_id": "a" * 32}
    )
    guarded = guard_changes(apply, req)
    assert "tool_calls" not in guarded["choices"][0]["message"]


def test_natural_approval_uses_the_previously_displayed_diff():
    req = proposed_request()
    display, _ = step(req)
    req["messages"].append(display["choices"][0]["message"])
    req["messages"].append({"role": "user", "content": "đồng ý áp dụng"})
    result, _ = step(req)
    assert action(result) == ("ollama_router_apply_changes", {"plan_id": "a" * 32})
    assert guard_changes(result, req) == result


def test_hidden_or_different_plan_is_not_approved_by_generic_ok():
    req = proposed_request()
    req["messages"].append({"role": "user", "content": "ok"})
    apply = completion(
        req, name="ollama_router_apply_changes", arguments={"plan_id": "b" * 32}
    )
    assert "tool_calls" not in guard_changes(apply, req)["choices"][0]["message"]


def test_analyzing_how_to_fix_a_file_does_not_request_an_edit():
    req = request("Phân tích app/server.py và giải thích cách sửa lỗi")
    read, _ = step(req)
    reply(req, read, {"content": "actual code"})
    result, hint = step(req)
    assert result is None and hint.startswith("Explain the actual files")


@pytest.mark.parametrize(
    "prompt", ["Không chạy test", "Don't run tests", "Đừng chạy kiểm thử"]
)
def test_negated_check_request_never_runs_checks(prompt):
    assert step(request(prompt)) == (None, None)
