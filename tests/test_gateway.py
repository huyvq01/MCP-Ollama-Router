import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from contextlib import AsyncExitStack

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr

from app.gateway import ManagedStream, create_app
from app.providers.ollama import OllamaProvider
from app.registry.schemas import ModelMetadata
from app.router.engine import RouterEngine
from app.runtime import RuntimeSettings
from app.services.history import HistoryManager

KEY = "test-key-not-used-outside-tests"
HEADERS = {"Authorization": "Bearer " + KEY}
TOOLS = [{"type": "function", "function": {
    "name": "read_file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
}}]


@pytest_asyncio.fixture
async def gateway():
    received = []
    state = {"mode": "text"}

    def handler(request):
        payload = json.loads(request.content)
        received.append(payload)
        if state["mode"] == "fail_once" and len(received) == 1:
            return httpx.Response(503, json={"error": "private-upstream-error"})
        if state["mode"] == "reject":
            return httpx.Response(400, json={"error": "private-upstream-error"})
        message = {"content": "Hello"}
        if state["mode"] == "tool":
            message = {"content": "", "tool_calls": [{"function": {
                "name": "read_file", "arguments": {"path": "README.md"},
            }}]}
        if payload["stream"]:
            events = [{"message": message, "done": False}]
            if state["mode"] != "incomplete":
                events.append({"done": True, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2})
            return httpx.Response(200, content="\n".join(json.dumps(event) for event in events))
        return httpx.Response(200, json={
            "message": message, "done": True, "done_reason": "stop",
            "prompt_eval_count": 5, "eval_count": 2,
        })

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider()
    provider.client = upstream
    providers = Mock()
    providers.get.return_value = provider
    providers.healthy = AsyncMock(return_value=["ollama"])
    registry = Mock()
    catalog = [
        ModelMetadata(provider="ollama", name="general:4b", parameter_size="4B", capabilities=["general"]),
        ModelMetadata(provider="ollama", name="coder:7b", parameter_size="7B", capabilities=["general", "code", "tools"]),
    ]
    registry.enabled.return_value = catalog
    registry.model.side_effect = lambda name: next((model for model in catalog if model.name == name), None)
    config = RuntimeSettings(_env_file=None, gateway_api_key=SecretStr(KEY), max_pending=1)
    router = RouterEngine(providers, registry, HistoryManager(), config=config)
    services = SimpleNamespace(provider_registry=providers, registry=registry, router=router)
    app = create_app(services, config)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, services, received, state
    await upstream.aclose()


@pytest.mark.asyncio
async def test_auth_and_models(gateway):
    client, _, received, _ = gateway
    assert (await client.get("/v1/models")).status_code == 401
    response = await client.get("/v1/models", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "auto"
    assert received == []
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/health/ready", headers=HEADERS)).status_code == 200


@pytest.mark.asyncio
async def test_chat_preserves_client_system_and_returns_usage(gateway):
    client, services, received, _ = gateway
    messages = [{"role": "system", "content": "Original company instructions"},
                {"role": "user", "content": "Java là gì?"}]
    response = await client.post("/v1/chat/completions", headers=HEADERS, json={"messages": messages})
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "general:4b"
    assert data["choices"][0]["message"]["content"] == "Hello"
    assert data["usage"]["total_tokens"] == 7
    assert received[0]["messages"] == messages
    assert services.router.gate._pending == 0


@pytest.mark.asyncio
async def test_tools_select_capable_model_and_roundtrip(gateway):
    client, _, received, state = gateway
    state["mode"] = "tool"
    payload = {"messages": [{"role": "user", "content": "Read README"}], "tools": TOOLS}
    first = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    data = first.json()
    assert data["model"] == "coder:7b"
    choice = data["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"path": "README.md"}
    state["mode"] = "text"
    payload["messages"] += [choice["message"], {
        "role": "tool", "tool_call_id": call["id"], "content": "# Project",
    }]
    second = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    assert second.status_code == 200
    assert received[-1]["messages"][-1]["tool_name"] == "read_file"
    assert isinstance(received[-1]["messages"][-2]["tool_calls"][0]["function"]["arguments"], dict)


@pytest.mark.asyncio
async def test_sse_text_usage_and_tool_calls(gateway):
    client, services, _, state = gateway
    payload = {"messages": [{"role": "user", "content": "hello"}], "stream": True,
               "stream_options": {"include_usage": True}}
    response = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    assert response.headers["content-type"].startswith("text/event-stream")
    lines = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "[DONE]"
    events = [json.loads(line) for line in lines[:-1]]
    assert events[1]["choices"][0]["delta"]["content"] == "Hello"
    assert events[-1]["usage"]["total_tokens"] == 7
    assert services.router.gate._pending == 0
    state["mode"] = "tool"
    payload["tools"] = TOOLS
    response = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    events = [json.loads(line[6:]) for line in response.text.splitlines()
              if line.startswith("data: ") and line != "data: [DONE]"]
    assert events[1]["choices"][0]["delta"]["tool_calls"][0]["index"] == 0
    assert events[2]["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.asyncio
async def test_broken_stream_is_explicit_and_does_not_retry(gateway):
    client, services, received, state = gateway
    state["mode"] = "incomplete"
    response = await client.post("/v1/chat/completions", headers=HEADERS, json={
        "messages": [{"role": "user", "content": "hello"}], "stream": True,
    })
    assert "upstream_stream_error" in response.text
    assert len(received) == 1
    assert services.router.gate._pending == 0


@pytest.mark.parametrize("extra", [
    {"model": "not-installed"}, {"max_tokens": 50000}, {"unexpected": True},
    {"tool_choice": "required"}, {"parallel_tool_calls": False},
    {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
    {"messages": [{"role": "tool", "tool_call_id": "missing", "content": "result"}]},
])
@pytest.mark.asyncio
async def test_invalid_options_fail_without_inference(gateway, extra):
    client, _, received, _ = gateway
    payload = {"messages": [{"role": "user", "content": "hello"}], **extra}
    response = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    assert response.status_code == 400
    assert received == []


@pytest.mark.asyncio
async def test_context_is_rejected_without_silent_truncation(gateway):
    client, _, received, _ = gateway
    response = await client.post("/v1/chat/completions", headers=HEADERS, json={
        "messages": [{"role": "system", "content": "secret" * 3000},
                     {"role": "user", "content": "hello"}],
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "context_length_exceeded"
    assert "secret" not in response.text
    assert received == []


@pytest.mark.asyncio
async def test_body_and_queue_limits(gateway):
    client, services, received, _ = gateway
    response = await client.post("/v1/chat/completions", headers=HEADERS, content=b"x" * 262145)
    assert response.status_code == 413
    async with services.router.gate.slot():
        response = await client.post("/v1/chat/completions", headers=HEADERS, json={
            "messages": [{"role": "user", "content": "hello"}],
        })
    assert response.status_code == 429
    assert received == []


@pytest.mark.asyncio
async def test_transient_fallback_but_permanent_errors_not_retried(gateway):
    client, services, received, state = gateway
    state["mode"] = "fail_once"
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    assert response.status_code == 200
    assert len(received) == 2
    received.clear()
    state["mode"] = "reject"
    response = await client.post("/v1/chat/completions", headers=HEADERS, json=payload)
    assert response.status_code == 502
    assert len(received) == 1
    assert "private-upstream-error" not in response.text
    assert services.router.gate._pending == 0


@pytest.mark.asyncio
async def test_disconnect_releases_stream_resources(gateway):
    _, services, _, _ = gateway
    stack = AsyncExitStack()
    await stack.enter_async_context(services.router.gate.slot())
    closed = []
    async def close():
        closed.append(True)
    stack.push_async_callback(close)
    async def content():
        yield "data: hello\n\n"
        await asyncio.sleep(10)
    response = ManagedStream(content(), stack, {})
    async def send(message):
        if message["type"] == "http.response.body":
            raise asyncio.CancelledError
    async def receive():
        return {"type": "http.disconnect"}
    with pytest.raises(asyncio.CancelledError):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert closed == [True]
    assert services.router.gate._pending == 0


@pytest.mark.asyncio
async def test_circuit_open_models_do_not_exhaust_attempt_budget(gateway):
    client, services, received, _ = gateway
    third = ModelMetadata(provider="ollama", name="third:5b", parameter_size="5B", capabilities=["general"])
    services.registry.enabled.return_value.append(third)
    ranked = services.router.selector.rank("hello")
    for model in ranked[:2]:
        for _ in range(2):
            services.router.breaker.failure(model.provider + ":" + model.name)
    response = await client.post("/v1/chat/completions", headers=HEADERS, json={
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert response.status_code == 200
    assert len(received) == 1
    assert response.json()["model"] == ranked[2].name


@pytest.mark.asyncio
async def test_upstream_malformed_json_is_502_not_invalid_client_request(gateway):
    client, services, _, _ = gateway
    provider = services.provider_registry.get("ollama")
    previous = provider.client
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="not JSON"),
    )) as malformed:
        provider.client = malformed
        response = await client.post("/v1/chat/completions", headers=HEADERS, json={
            "messages": [{"role": "user", "content": "hello"}],
        })
    provider.client = previous
    assert response.status_code == 502
    assert services.router.gate._pending == 0
