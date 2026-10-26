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
    upstream = "http://127.0.0.1:11434"

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
        payload = {**request, "stream": False}
        payload.pop("stream_options", None)
        try:
            with httpx.Client(trust_env=False, timeout=180) as client:
                response = client.post(
                    self.upstream + "/v1/chat/completions", json=payload
                )
                result = response.json()
            if response.status_code != 200:
                self.send_json(response.status_code, result)
                return
            result = normalize_completion(result, request)
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
    parser.add_argument("--port", type=int, default=18080)
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
