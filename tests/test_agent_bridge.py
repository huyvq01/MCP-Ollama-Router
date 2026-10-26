import json

import pytest

from app.agent_bridge import completion_events, normalize_completion


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
