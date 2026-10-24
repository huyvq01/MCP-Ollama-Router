import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.models.chat import ChatResult
from app.registry.schemas import ModelMetadata
from app.router.engine import RouterEngine
from app.runtime import RuntimeSettings, env_file_path
from app.services.control import BusyError, CircuitBreaker, RequestGate, RoutingTimeout
from app.services.history import HistoryManager
from app.services.token_budget import estimate_tokens, truncate_text_to_tokens


def config(**kwargs):
    return RuntimeSettings(_env_file=None, **kwargs)


@pytest.mark.parametrize("values", [
    {"max_pending": 1, "max_concurrent": 2},
    {"context_tokens": 2048, "max_output_tokens": 2048},
    {"ollama_base_url": "file:///tmp/model"},
    {"ollama_base_url": "http://user:password@localhost:11434"},
    {"log_level": "INVALID"},
])
def test_invalid_config_fails_fast(values):
    with pytest.raises(ValidationError):
        config(**values)


def test_env_path_editable_install(monkeypatch, tmp_path):
    monkeypatch.delenv("ROUTER_ENV_FILE", raising=False)
    (tmp_path / "pyproject.toml").write_text("")
    assert env_file_path(tmp_path) == tmp_path / ".env"


def test_env_path_wheel_install(monkeypatch, tmp_path):
    monkeypatch.delenv("ROUTER_ENV_FILE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert env_file_path(tmp_path / "site-packages") == tmp_path / ".env"


def test_env_path_explicit_override(monkeypatch, tmp_path):
    target = tmp_path / "operator.env"
    monkeypatch.setenv("ROUTER_ENV_FILE", str(target))
    assert env_file_path(tmp_path / "site-packages") == target


def test_history_is_bounded_copy_on_read_and_non_creating():
    history = HistoryManager(max_sessions=2)
    assert history.get("missing") == []
    assert history.sessions() == []
    for key in ("a", "b", "c"):
        history.append(key, "user", "hello")
    assert history.sessions() == ["b", "c"]
    snapshot = history.get("b")
    snapshot[0]["content"] = "changed outside history"
    assert history.get("b")[0]["content"] == "hello"


def test_history_expiry_and_clear_prevent_resurrection(monkeypatch):
    import app.services.history as module
    clock = [1.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    history = HistoryManager(ttl=5)
    revision = history.revision("a")
    history.clear("a")
    assert not history.append_turn("a", "question", "answer", expected_revision=revision)
    replacement = history.revision("a")
    assert replacement != revision
    assert not history.append_turn("a", "stale", "answer", expected_revision=revision)
    clock[0] += 6
    assert history.sessions() == []


@pytest.mark.parametrize("text", ["Tiếng Việt có dấu " * 1000, "你好🙂" * 1000, "code" * 1000],
                         ids=["vietnamese", "cjk-emoji", "ascii"])
def test_unicode_truncation_respects_estimator(text):
    result = truncate_text_to_tokens(text, 100)
    assert estimate_tokens(result) <= 100
    assert "\ufffd" not in result


@pytest.mark.asyncio
async def test_gate_rejects_overload_and_releases_after_cancellation():
    gate = RequestGate(config(max_concurrent=1, max_pending=2, queue_timeout_s=1))
    entered = asyncio.Event()
    async def waiter():
        entered.set()
        async with gate.slot():
            pass
    async with gate.slot():
        pending = asyncio.create_task(waiter())
        await entered.wait()
        await asyncio.sleep(0)
        with pytest.raises(BusyError):
            async with gate.slot():
                pass
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    assert gate._pending == 0
    async with gate.slot():
        assert gate._pending == 1


def test_breaker_cooldown(monkeypatch):
    import app.services.control as module
    clock = [100.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    breaker = CircuitBreaker(config(breaker_failures=2, breaker_cooldown_s=5))
    breaker.failure("model")
    assert breaker.available("model")
    breaker.failure("model")
    assert not breaker.available("model")
    clock[0] += 6
    assert breaker.available("model")


def engine(provider, **values):
    providers = Mock()
    providers.get.return_value = provider
    registry = Mock()
    model = ModelMetadata(provider="ollama", name="test:3b", capabilities=["general"])
    registry.enabled.return_value = [model]
    history = HistoryManager()
    return RouterEngine(providers, registry, history, config=config(**values)), history


@pytest.mark.asyncio
async def test_same_session_turns_are_serialized():
    observed = []
    async def chat(request):
        observed.append(request.messages)
        await asyncio.sleep(0.01)
        return ChatResult(provider="ollama", model=request.model, content="answer")
    provider = Mock()
    provider.chat = chat
    router, history = engine(provider, max_concurrent=2)
    await asyncio.gather(router.chat("same", "first"), router.chat("same", "second"))
    assert len(observed) == 2
    assert any(item["content"] == "first" for item in observed[1])
    assert [item["role"] for item in history.get("same")] == [
        "user", "assistant", "user", "assistant",
    ]
    assert router._sessions._entries == {}


@pytest.mark.asyncio
async def test_total_deadline_cancels_provider_and_releases_slots():
    async def slow(request):
        await asyncio.sleep(10)
    provider = Mock()
    provider.chat = slow
    router, history = engine(provider, request_timeout_s=0.02, attempt_timeout_s=1)
    with pytest.raises(RoutingTimeout):
        await router.chat("slow", "hello")
    assert router.gate._pending == 0
    assert router._sessions._entries == {}
    assert history.get("slow") == []


@pytest.mark.asyncio
async def test_no_cross_session_history_and_no_prompt_logging(caplog):
    provider = Mock()
    provider.chat = AsyncMock(return_value=ChatResult(provider="ollama", model="test:3b", content="answer"))
    router, history = engine(provider)
    history.append("other", "user", "company-secret-do-not-log")
    with caplog.at_level("INFO"):
        await router.chat("fresh", "new-secret-do-not-log")
    request = provider.chat.await_args.args[0]
    assert not any("company-secret" in message["content"] for message in request.messages)
    assert "secret-do-not-log" not in caplog.text


@pytest.mark.asyncio
async def test_mcp_rejects_truncated_review_without_calling_model():
    provider = Mock()
    provider.chat = AsyncMock()
    router, _ = engine(provider)
    with pytest.raises(ValueError, match="smaller excerpt"):
        await router.chat("review", "x" * 15000)
    provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_upstream_payload_can_fall_back():
    provider = Mock()
    provider.chat = AsyncMock(side_effect=[
        ValueError("invalid JSON"),
        ChatResult(provider="ollama", model="backup:3b", content="answer"),
    ])
    router, _ = engine(provider)
    router._registry.enabled.return_value.append(ModelMetadata(
        provider="ollama", name="backup:3b", capabilities=["general"],
    ))
    assert await router.chat("fallback", "hello") == "answer"
    assert provider.chat.await_count == 2
