import json

import pytest

from app.agent_bridge import completion_events, ensure_tool_answer, normalize_completion


def request():
    return {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
    }


def completion(text, finish="stop"):
    return {
        "id": "test",
        "model": "local",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish,
            }
        ],
    }


@pytest.mark.parametrize(
    "wrapper", ["{}", "```json\n{}\n```", "<tool_call>{}</tool_call>"]
)
def test_promotes_exact_schema_valid_calls(wrapper):
    text = wrapper.format(
        json.dumps({"name": "read_file", "arguments": {"path": "app/server.py"}})
    )
    result = normalize_completion(completion(text), request())
    choice = result["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"path": "app/server.py"}
    assert call["id"].startswith("call_")
    events = list(completion_events(result))
    assert events[0]["choices"][0]["delta"]["tool_calls"][0]["index"] == 0
    assert events[1]["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.parametrize(
    "text",
    [
        'Use this example: {"name":"read_file","arguments":{"path":"x"}}',
        '{"name":"shell","arguments":{"path":"x"}}',
        '{"name":"read_file","arguments":{"filepath":"x"}}',
        '{"name":"read_file","arguments":{"path":12}}',
        '{"name":"read_file","arguments":{"path":"x"},"extra":true}',
        "[]",
        "Hello",
    ],
)
def test_does_not_turn_examples_or_invalid_calls_into_actions(text):
    original = completion(text)
    assert normalize_completion(original, request()) == original


def test_respects_disabled_tools_and_truncation():
    original = completion('{"name":"read_file","arguments":{"path":"x"}}')
    assert (
        normalize_completion(original, {**request(), "tool_choice": "none"}) == original
    )
    truncated = completion(original["choices"][0]["message"]["content"], "length")
    assert normalize_completion(truncated, request()) == truncated


def test_preserves_native_calls_and_tool_history():
    original = completion(None, "tool_calls")
    original["choices"][0]["message"]["tool_calls"] = [
        {
            "id": "original",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path":"x"}'},
        }
    ]
    assert normalize_completion(original, request()) == original


def tool_history():
    return {
        "messages": [
            {"role": "user", "content": "Show actual model"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "metrics-1",
                        "type": "function",
                        "function": {
                            "name": "chat_metrics",
                            "arguments": '{"session_id":"report-1"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "metrics-1",
                "content": '{"model":"qwen2.5-coder:7b"}',
            },
        ]
    }


@pytest.mark.parametrize("content", [None, "", "  "])
def test_empty_model_answer_displays_real_tool_result_in_sse(content):
    original = completion(content)
    result = ensure_tool_answer(original, tool_history())
    assert original["choices"][0]["message"]["content"] == content
    text = result["choices"][0]["message"]["content"]
    assert '{"model":"qwen2.5-coder:7b"}' in text
    assert list(completion_events(result))[0]["choices"][0]["delta"]["content"] == text
    assert result["bridge_tool_result_fallback"] is True


def test_repeat_completed_call_returns_output_without_running_it_again():
    result = completion(None, "tool_calls")
    result["choices"][0]["message"]["tool_calls"] = [
        {
            "id": "new-id",
            "type": "function",
            "function": {
                "name": "chat_metrics",
                "arguments": '{ "session_id": "report-1" }',
            },
        }
    ]
    repaired = ensure_tool_answer(result, tool_history())
    assert "tool_calls" not in repaired["choices"][0]["message"]
    assert repaired["choices"][0]["finish_reason"] == "stop"


@pytest.mark.parametrize(
    "scenario", ["new_user", "wrong_id", "empty_tool", "no_history"]
)
def test_never_reuses_missing_or_stale_results(scenario):
    request_data = tool_history()
    if scenario == "new_user":
        request_data["messages"].append({"role": "user", "content": "Ask again"})
    elif scenario == "wrong_id":
        request_data["messages"][-1]["tool_call_id"] = "unknown"
    elif scenario == "empty_tool":
        request_data["messages"][-1]["content"] = ""
    else:
        request_data = {}
    original = completion("")
    assert ensure_tool_answer(original, request_data) == original


def test_preserves_model_answer_and_new_tool_requests():
    original = completion("Here is the answer")
    assert ensure_tool_answer(original, tool_history()) == original
    new_call = completion(None, "tool_calls")
    new_call["choices"][0]["message"]["tool_calls"] = [
        {
            "id": "new",
            "function": {
                "name": "chat_metrics",
                "arguments": '{"session_id":"different-session"}',
            },
        }
    ]
    assert ensure_tool_answer(new_call, tool_history()) == new_call


def test_refusal_is_not_replaced_with_tool_output():
    original = completion(None, "stop")
    original["choices"][0]["message"]["refusal"] = "Cannot answer"
    assert ensure_tool_answer(original, tool_history()) == original


def test_waits_for_all_parallel_tool_replies():
    request_data = tool_history()
    request_data["messages"][1]["tool_calls"].append(
        {"id": "pending", "function": {"name": "chat_metrics", "arguments": "{}"}}
    )
    original = completion("")
    assert ensure_tool_answer(original, request_data) == original
