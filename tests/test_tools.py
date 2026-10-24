from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from app.registry.schemas import ModelMetadata
from app.tools import chat as chat_tools
from app.tools import health as health_tools
from app.tools import models as model_tools
from app.tools import register_all
from app.tools import system as system_tools


class FakeServer:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(
        self,
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        self.tools[func.__name__] = func
        return func


@pytest.mark.asyncio
async def test_chat_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    server = FakeServer()

    router = Mock()
    router.chat = AsyncMock(return_value="Hello User")

    monkeypatch.setattr(
        chat_tools.container,
        "router",
        router,
    )

    chat_tools.register(server)  # type: ignore[arg-type]

    result = await server.tools["chat"](
        session_id="demo",
        prompt="Hello",
        model="qwen2.5-coder:7b",
    )

    assert result == "Hello User"

    router.chat.assert_awaited_once_with(
        session_id="demo",
        prompt="Hello",
        model="qwen2.5-coder:7b",
    )


@pytest.mark.asyncio
async def test_chat_tool_forwards_output_limit(monkeypatch):
    server = FakeServer()
    router = Mock()
    router.chat = AsyncMock(return_value="OK")
    monkeypatch.setattr(chat_tools.container, "router", router)
    chat_tools.register(server)
    assert await server.tools["chat"](
        session_id="fast", prompt="Hello", max_tokens=128,
    ) == "OK"
    router.chat.assert_awaited_once_with(
        session_id="fast", prompt="Hello", model=None, max_tokens=128,
    )


def test_clear_chat_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    router = Mock()

    monkeypatch.setattr(
        chat_tools.container,
        "router",
        router,
    )

    chat_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["clear_chat"](
        session_id="demo",
    )

    assert result == "Conversation cleared."

    router.clear.assert_called_once_with("demo")


def test_list_sessions_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    router = Mock()
    router.sessions.return_value = [
        "session-1",
        "session-2",
    ]

    monkeypatch.setattr(
        chat_tools.container,
        "router",
        router,
    )

    chat_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["list_sessions"]()

    assert result == [
        "session-1",
        "session-2",
    ]


@pytest.mark.asyncio
async def test_health_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    provider_registry = Mock()
    provider_registry.healthy = AsyncMock(
        return_value=["ollama"],
    )

    monkeypatch.setattr(
        health_tools.container,
        "provider_registry",
        provider_registry,
    )

    health_tools.register(server)  # type: ignore[arg-type]

    result = await server.tools["health"]()

    assert result == {
        "providers": ["ollama"],
        "count": 1,
    }

    provider_registry.healthy.assert_awaited_once()


def test_list_models_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    models = [
        ModelMetadata(
            provider="ollama",
            name="qwen2.5-coder:7b",
            capabilities=["general", "code"],
            priority=100,
        ),
        ModelMetadata(
            provider="ollama",
            name="deepseek-r1:14b",
            capabilities=["general", "reasoning"],
            priority=95,
        ),
    ]

    registry = Mock()
    registry.models.return_value = models

    monkeypatch.setattr(
        model_tools.container,
        "registry",
        registry,
    )

    model_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["list_models"]()

    assert result == models

    registry.models.assert_called_once_with()


def test_show_model_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    model = ModelMetadata(
        provider="ollama",
        name="qwen2.5-coder:7b",
        capabilities=["general", "code"],
        priority=100,
    )

    registry = Mock()
    registry.model.return_value = model

    monkeypatch.setattr(
        model_tools.container,
        "registry",
        registry,
    )

    model_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["show_model"](
        model="qwen2.5-coder:7b",
    )

    assert result == model

    registry.model.assert_called_once_with("qwen2.5-coder:7b")


def test_show_model_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    registry = Mock()
    registry.model.return_value = None

    monkeypatch.setattr(
        model_tools.container,
        "registry",
        registry,
    )

    model_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["show_model"](
        model="unknown",
    )

    assert result is None


def test_clear_cache_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = FakeServer()

    cache = Mock()

    monkeypatch.setattr(
        system_tools.container,
        "cache",
        cache,
    )

    system_tools.register(server)  # type: ignore[arg-type]

    result = server.tools["clear_cache"]()

    assert result == "Cache cleared."

    cache.clear.assert_called_once_with()


def test_register_all() -> None:
    server = FakeServer()

    register_all(server)  # type: ignore[arg-type]

    assert set(server.tools) == {
        "chat",
        "clear_chat",
        "list_sessions",
        "health",
        "list_models",
        "show_model",
        "clear_cache",
        "route_preview",
    }
