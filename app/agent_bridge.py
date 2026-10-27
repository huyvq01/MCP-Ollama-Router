"""Loopback OpenAI API adapter for Ollama's text-only function calls.

Run with python -m app.agent_bridge. This service never executes tools.
"""

import argparse
import copy
import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from jsonschema import ValidationError, validate

from app.agent_workflow import guard_changes, prepare, step
from app.core.settings import settings


def normalize_completion(result: dict, request: dict) -> dict:
    """Promote only complete, schema-valid calls to advertised functions."""
    result = copy.deepcopy(result)
    functions = {
        tool["function"]["name"]: tool["function"]
        for tool in request.get("tools", [])
        if tool.get("type") == "function"
    }
    if not functions or request.get("tool_choice") == "none":
        return result
    for choice in result.get("choices", []):
        message = choice.get("message", {})
        if message.get("tool_calls"):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        candidate = content.strip()
        if candidate.startswith("```json") and candidate.endswith("```"):
            candidate = candidate[7:-3].strip()
        elif candidate.startswith("```") and candidate.endswith("```"):
            candidate = candidate[3:-3].strip()
        tags = re.fullmatch(r"(?:\s*<tool_call>.*?</tool_call>\s*)+", candidate, re.S)
        try:
            raw = (
                [
                    json.loads(item)
                    for item in re.findall(
                        r"<tool_call>(.*?)</tool_call>", candidate, re.S
                    )
                ]
                if tags
                else json.loads(candidate)
            )
            calls = raw if isinstance(raw, list) else [raw]
            if not calls:
                continue
            converted = []
            for call in calls:
                if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
                    raise ValueError("Not a function call")
                name, arguments = call["name"], call["arguments"]
                if not isinstance(name, str) or name not in functions:
                    raise ValueError("Unknown function")
                if not isinstance(arguments, dict):
                    raise ValueError("Arguments must be an object")
                validate(
                    arguments, functions[name].get("parameters", {"type": "object"})
                )
                converted.append(
                    {
                        "id": "call_" + uuid.uuid4().hex,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                )
            # Never promote an incomplete/truncated generation.
            if choice.get("finish_reason") != "stop":
                continue
            message["content"] = None
            message["tool_calls"] = converted
            choice["finish_reason"] = "tool_calls"
        except (ValueError, TypeError, ValidationError):
            continue
    return result


def completed_tool_results(request: dict) -> list[tuple[dict, str]]:
    """Use only matched tool replies at the end of this request's history."""
    messages = request.get("messages", [])
    replies = []
    cursor = len(messages) - 1
    while cursor >= 0 and messages[cursor].get("role") == "tool":
        replies.append(messages[cursor])
        cursor -= 1
    if not replies or cursor < 0:
        return []
    assistant = messages[cursor]
    if assistant.get("role") != "assistant":
        return []
    calls = {call.get("id"): call for call in assistant.get("tool_calls", [])}
    if {reply.get("tool_call_id") for reply in replies} != set(calls):
        return []
    completed = []
    for reply in reversed(replies):
        call = calls.get(reply.get("tool_call_id"))
        content = reply.get("content")
        if not call or not isinstance(content, str) or not content.strip():
            return []
        completed.append((call, content))
    return completed


def function_signature(call: dict) -> tuple[str, str] | None:
    function = call.get("function", {})
    name = function.get("name")
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (ValueError, TypeError):
        return None
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return None
    return name, json.dumps(arguments, sort_keys=True, ensure_ascii=True)


def ensure_tool_answer(result: dict, request: dict) -> dict:
    """Surface actual tool output if the model stops empty or repeats completed calls.

    Never invent an answer, execute a tool, or reuse results across a new user turn.
    """
    completed = completed_tool_results(request)
    if not completed:
        return result
    signatures = {function_signature(call) for call, _ in completed}
    signatures.discard(None)
    result = copy.deepcopy(result)
    for choice in result.get("choices", []):
        message = choice.get("message", {})
        if message.get("refusal"):
            continue
        calls = message.get("tool_calls", [])
        repeated = bool(calls) and all(
            function_signature(call) in signatures for call in calls
        )
        empty = not calls and not (message.get("content") or "").strip()
        if not (
            repeated or (empty and choice.get("finish_reason") in {"stop", "length"})
        ):
            continue
        message.pop("tool_calls", None)
        message["content"] = "\n\n".join(
            f"Tool result ({call['function']['name']}):\n{content}"
            for call, content in completed
        )
        choice["finish_reason"] = "stop"
        # Usage remains the upstream generation's token count, not this verbatim copy.
        result["bridge_tool_result_fallback"] = True
    return result


def completion_events(result: dict):
    """Emit buffered completions as OpenAI SSE, including function-call deltas."""
    for choice in result.get("choices", []):
        message = copy.deepcopy(choice["message"])
        for index, call in enumerate(message.get("tool_calls", [])):
            call["index"] = index
        base = {key: result[key] for key in ("id", "created", "model") if key in result}
        base["object"] = "chat.completion.chunk"
        yield {
            **base,
            "choices": [
                {
                    "index": choice.get("index", 0),
                    "delta": message,
                    "finish_reason": None,
                }
            ],
        }
        yield {
            **base,
            "choices": [
                {
                    "index": choice.get("index", 0),
                    "delta": {},
                    "finish_reason": choice.get("finish_reason", "stop"),
                }
            ],
        }
    if result.get("usage"):
        yield {**base, "choices": [], "usage": result["usage"]}


class Handler(BaseHTTPRequestHandler):
    upstream = settings.ollama_host.rstrip("/")

    def log_message(self, *_args):
        pass  # Do not log prompts, paths or tool arguments.

    def send_json(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_json(404, {"error": {"message": "Unknown endpoint"}})
            return
        try:
            with httpx.Client(trust_env=False, timeout=10) as client:
                response = client.get(self.upstream + "/v1/models")
                self.send_json(response.status_code, response.json())
        except (httpx.HTTPError, ValueError):
            self.send_json(502, {"error": {"message": "Ollama unavailable"}})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_json(404, {"error": {"message": "Unknown endpoint"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8_000_000:
                self.send_json(413, {"error": {"message": "Invalid request size"}})
                return
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError("Expected object")
        except (ValueError, TypeError):
            self.send_json(400, {"error": {"message": "Invalid JSON request"}})
            return
        stream = request.get("stream", False)
        try:
            planned, hint = (
                step(request) if settings.bridge_auto_tools else (None, None)
            )
            if planned is not None:
                result = planned
            else:
                payload = (
                    prepare(request, hint)
                    if settings.bridge_auto_tools
                    else dict(request)
                )
                payload["stream"] = False
                payload.pop("stream_options", None)
                with httpx.Client(trust_env=False, timeout=180) as client:
                    response = client.post(
                        self.upstream + "/v1/chat/completions", json=payload
                    )
                    result = response.json()
                if response.status_code != 200:
                    self.send_json(response.status_code, result)
                    return
            result = normalize_completion(result, request)
            if settings.bridge_auto_tools:
                result = guard_changes(result, request)
            result = ensure_tool_answer(result, request)
        except (httpx.HTTPError, ValueError):
            self.send_json(502, {"error": {"message": "Ollama request failed"}})
            return
        if not stream:
            self.send_json(200, result)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for event in completion_events(result):
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=settings.bridge_port)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Agent bridge: http://127.0.0.1:{args.port}/v1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
