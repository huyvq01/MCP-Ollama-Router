import asyncio
import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.core.settings import settings
from app.models.chat import ChatRequest, ChatResult
from app.prompts.message import MessageBuilder
from app.providers.ollama import OllamaProvider
from app.registry.schemas import ModelMetadata
from app.router.engine import RouterEngine
from app.router.matcher import matcher
from app.router.selector import ModelSelector
from app.services.history import HistoryManager


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("good morning", "general"),
        ("Summarize digital transformation", "summarize"),
        ("Write a report about Java architecture", "report"),
        ("Viết báo cáo Mendix", "report"),
        ("Fix Java action", "code"),
        ("Viết microflow", "code"),
    ],
)
def test_routing_word_boundaries(prompt, expected):
    assert matcher.match(prompt).value == expected


def test_oversize_prompt_is_rejected():
    with pytest.raises(ValueError, match="context budget"):
        MessageBuilder().build([], "x" * settings.num_ctx)


def test_budget_preserves_complete_recent_turns():
    history = [
        {"role": "user", "content": "old" * 2000},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "recent"},
        {"role": "assistant", "content": "recent answer"},
    ]
    result = MessageBuilder().build(history, "next")
    assert [m["content"] for m in result[1:-1]] == ["recent", "recent answer"]
    assert (
        sum(len(m["content"].encode("utf-8")) + 16 for m in result)
        + settings.max_tokens
        + 256
        <= settings.num_ctx
    )


def test_history_sessions_bounded_and_get_does_not_create(monkeypatch):
    monkeypatch.setattr(settings, "max_sessions", 2)
    h = HistoryManager()
    assert h.get("missing") == []
    assert h.sessions() == []
    for key in ("a", "b", "c"):
        h.append(key, "user", key)
    assert h.sessions() == ["b", "c"]


def test_history_copy_does_not_mutate_storage():
    h = HistoryManager()
    h.append("a", "user", "hello")
    h.get("a")[0]["content"] = "modified"
    assert h.get("a")[0]["content"] == "hello"


async def test_preferred_fast_model_wins_over_7b():
    r = Mock()
    r.enabled.return_value = [
        ModelMetadata(
            provider="ollama",
            name="qwen2.5-coder:7b",
            capabilities=["code"],
            priority=200,
        ),
        ModelMetadata(
            provider="ollama",
            name=settings.default_model,
            capabilities=["code"],
            priority=100,
        ),
    ]
    assert (await ModelSelector(r).select("write Java")).name == settings.default_model


async def test_provider_sends_resource_limits_and_stop_reason():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"content": "answer"},
                "done": True,
                "done_reason": "length",
                "eval_count": 12,
            },
        )

    p = OllamaProvider()
    p.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await p.chat(ChatRequest(model="test", messages=[], max_tokens=32))
        assert seen["options"]["num_ctx"] == settings.num_ctx
        assert seen["options"]["num_predict"] == 32
        assert seen["keep_alive"] == settings.keep_alive
        assert seen["stream"] is False
        assert result.finish_reason == "length"
        with pytest.raises(ValueError, match="Streaming"):
            await p.chat(ChatRequest(model="test", messages=[], stream=True))
    finally:
        await p.shutdown()


def setup_router():
    p = AsyncMock()
    pr = Mock()
    pr.get.return_value = p
    m = ModelMetadata(
        provider="ollama", name=settings.default_model, capabilities=["general", "code"]
    )
    r = Mock()
    r.model.return_value = m
    r.enabled.return_value = [m]
    return RouterEngine(pr, r, HistoryManager()), p


async def test_explicit_model_failure_does_not_silently_switch():
    router, p = setup_router()
    p.chat.side_effect = RuntimeError("failure")
    with pytest.raises(RuntimeError, match="failure"):
        await router.chat("a", "hello", model=settings.default_model)
    assert p.chat.await_count == 1
    assert router.sessions() == []


async def test_busy_request_fails_fast_and_cancellation_releases_gate():
    router, p = setup_router()
    entered = asyncio.Event()

    async def wait(_):
        entered.set()
        await asyncio.Event().wait()

    p.chat.side_effect = wait
    task = asyncio.create_task(router.chat("a", "hello"))
    await entered.wait()
    with pytest.raises(RuntimeError, match="busy"):
        await router.chat("b", "hello")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not router._gate.locked()


async def test_transport_timeout_is_not_retried():
    router, p = setup_router()
    p.chat.side_effect = httpx.ReadTimeout("slow")
    with pytest.raises(RuntimeError, match="ReadTimeout"):
        await router.chat("a", "hello")
    assert p.chat.await_count == 1


async def test_total_deadline(monkeypatch):
    router, p = setup_router()
    monkeypatch.setattr(settings, "timeout", 0.01)

    async def wait(_):
        await asyncio.Event().wait()

    p.chat.side_effect = wait
    with pytest.raises(RuntimeError, match="exceeded"):
        await router.chat("a", "hello")
    assert not router._gate.locked()


async def test_report_mode_and_metrics():
    router, p = setup_router()
    p.chat.return_value = ChatResult(
        provider="ollama",
        model=settings.default_model,
        content="Report",
        finish_reason="length",
        completion_tokens=50,
    )
    assert await router.chat("a", "Viết báo cáo Mendix") == "Report"
    request = p.chat.call_args.args[0]
    assert request.temperature == 0.3
    assert "Never invent citations" in request.messages[0]["content"]
    assert router.metrics("a")["finish_reason"] == "length"


async def test_failure_does_not_escalate_from_3b_to_7b():
    router, provider = setup_router()
    provider.chat.side_effect = RuntimeError("failed")
    small = ModelMetadata(
        provider="ollama", name=settings.default_model, capabilities=["code"]
    )
    large = ModelMetadata(
        provider="ollama", name="qwen2.5-coder:7b", capabilities=["code"]
    )
    router._registry.enabled.return_value = [small, large]
    with pytest.raises(RuntimeError, match="failed"):
        await router.chat("a", "write Java")
    assert provider.chat.await_count == 1
