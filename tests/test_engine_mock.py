from unittest.mock import AsyncMock, Mock

import pytest

from app.models.chat import ChatResult
from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.engine import RouterEngine
from app.services.history import HistoryManager


def make_model(
    name: str,
    priority: int = 100,
    provider: str = "ollama",
) -> ModelMetadata:
    return ModelMetadata(
        provider=provider,
        name=name,
        capabilities=["general"],
        priority=priority,
    )


@pytest.mark.asyncio
async def test_chat(monkeypatch):
    provider = AsyncMock()

    provider.chat.return_value = ChatResult(
        provider="ollama",
        model="qwen2.5-coder:7b",
        content="Hello User",
        finish_reason="stop",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        latency_ms=10,
    )

    provider_registry = Mock(spec=ProviderRegistry)
    provider_registry.get.return_value = provider

    registry = Mock(spec=RegistryService)

    selected = make_model(
        "qwen2.5-coder:7b",
        priority=100,
    )

    registry.enabled.return_value = [selected]
    registry.model.return_value = selected

    history = Mock(spec=HistoryManager)
    history.get.return_value = []

    router = RouterEngine(
        provider_registry=provider_registry,
        registry=registry,
        history=history,
    )

    monkeypatch.setattr(
        router.selector,
        "select",
        AsyncMock(return_value=selected),
    )

    from app.router import engine

    monkeypatch.setattr(
        engine.builder,
        "build",
        lambda history, prompt: [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    answer = await router.chat(
        "demo",
        "Hello",
    )

    assert answer == "Hello User"

    provider.chat.assert_awaited_once()

    history.append.assert_any_call(
        "demo",
        "user",
        "Hello",
    )

    history.append.assert_any_call(
        "demo",
        "assistant",
        "Hello User",
    )


@pytest.mark.asyncio
async def test_chat_unknown_model():
    provider_registry = Mock(spec=ProviderRegistry)

    registry = Mock(spec=RegistryService)
    registry.model.return_value = None

    history = Mock(spec=HistoryManager)

    router = RouterEngine(
        provider_registry=provider_registry,
        registry=registry,
        history=history,
    )

    with pytest.raises(
        RuntimeError,
        match="Model 'unknown' not found.",
    ):
        await router.chat(
            session_id="demo",
            prompt="Hello",
            model="unknown",
        )


@pytest.mark.asyncio
async def test_chat_provider_not_found(monkeypatch):
    provider_registry = Mock(spec=ProviderRegistry)
    provider_registry.get.return_value = None

    registry = Mock(spec=RegistryService)

    selected = make_model("qwen")

    registry.enabled.return_value = [selected]

    history = Mock(spec=HistoryManager)
    history.get.return_value = []

    router = RouterEngine(
        provider_registry=provider_registry,
        registry=registry,
        history=history,
    )

    monkeypatch.setattr(
        router.selector,
        "select",
        AsyncMock(return_value=selected),
    )

    from app.router import engine

    monkeypatch.setattr(
        engine.builder,
        "build",
        lambda *_: [],
    )

    with pytest.raises(
        RuntimeError,
        match="No available model could complete the request.",
    ):
        await router.chat(
            "demo",
            "hello",
        )


@pytest.mark.asyncio
async def test_chat_fallback(monkeypatch):
    provider = AsyncMock()

    provider.chat.side_effect = [
        RuntimeError("primary failed"),
        ChatResult(
            provider="ollama",
            model="deepseek",
            content="fallback success",
            finish_reason="stop",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            latency_ms=10,
        ),
    ]

    provider_registry = Mock(spec=ProviderRegistry)
    provider_registry.get.return_value = provider

    first = make_model(
        "qwen",
        priority=100,
    )

    second = make_model(
        "deepseek",
        priority=90,
    )

    registry = Mock(spec=RegistryService)
    registry.enabled.return_value = [
        first,
        second,
    ]

    history = Mock(spec=HistoryManager)
    history.get.return_value = []

    router = RouterEngine(
        provider_registry=provider_registry,
        registry=registry,
        history=history,
    )

    monkeypatch.setattr(
        router.selector,
        "select",
        AsyncMock(return_value=first),
    )

    from app.router import engine

    monkeypatch.setattr(
        engine.builder,
        "build",
        lambda *_: [],
    )

    answer = await router.chat(
        "demo",
        "hello",
    )

    assert answer == "fallback success"

    assert provider.chat.await_count == 2


@pytest.mark.asyncio
async def test_chat_all_models_failed(monkeypatch):
    provider = AsyncMock()

    provider.chat.side_effect = RuntimeError("network")

    provider_registry = Mock(spec=ProviderRegistry)
    provider_registry.get.return_value = provider

    first = make_model(
        "qwen",
        priority=100,
    )

    second = make_model(
        "deepseek",
        priority=90,
    )

    registry = Mock(spec=RegistryService)
    registry.enabled.return_value = [
        first,
        second,
    ]

    history = Mock(spec=HistoryManager)
    history.get.return_value = []

    router = RouterEngine(
        provider_registry=provider_registry,
        registry=registry,
        history=history,
    )

    monkeypatch.setattr(
        router.selector,
        "select",
        AsyncMock(return_value=first),
    )

    from app.router import engine

    monkeypatch.setattr(
        engine.builder,
        "build",
        lambda *_: [],
    )

    with pytest.raises(
        RuntimeError,
        match="No available model could complete the request.",
    ):
        await router.chat(
            "demo",
            "hello",
        )

    assert provider.chat.await_count == 2
