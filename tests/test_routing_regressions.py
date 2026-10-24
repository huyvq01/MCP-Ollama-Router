import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.models.chat import ChatResult
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.registry.storage import RegistryStorage
from app.router.engine import RouterEngine
from app.router.model_size import parameter_billions
from app.router.policy import RoutingPolicy
from app.services.history import HistoryManager


@pytest.mark.parametrize(
    ("name", "metadata", "expected"),
    [
        ("custom", "13B", 13.0),
        ("model:3b", "72B", 72.0),
        ("model:13b", "", 13.0),
        ("model:30b", "", 30.0),
        ("model:72b", "", 72.0),
        ("model:1.5b", "", 1.5),
        ("custom", "500M", 0.5),
        ("custom", "1T", 1000.0),
        ("model:8b", "unknown", 8.0),
        ("custom", "", None),
    ],
)
def test_model_size(name, metadata, expected):
    model = ModelMetadata(provider="ollama", name=name, parameter_size=metadata)
    assert parameter_billions(model) == expected
    assert RouterEngine._is_unsupported_large_model(model) == (
        expected is not None and expected > 8
    )
    assert RoutingPolicy._model_size(model) == (
        expected if expected is not None else 999.0
    )


@pytest.mark.asyncio
async def test_fallback_reaches_higher_priority_model():
    selected = ModelMetadata(provider="ollama", name="coder:7b", priority=90)
    backup = ModelMetadata(provider="ollama", name="general:3b", priority=120)
    provider = Mock()
    provider.chat = AsyncMock(side_effect=[
        RuntimeError("primary unavailable"),
        ChatResult(provider="ollama", model=backup.name, content="OK"),
    ])
    providers = Mock()
    providers.get.return_value = provider
    registry = Mock()
    registry.model.return_value = selected
    registry.enabled.return_value = [backup, selected]
    history = HistoryManager()
    router = RouterEngine(providers, registry, history)

    assert await router.chat(
        "regression", "Hello", model=selected.name, max_tokens=128,
    ) == "OK"
    assert [call.args[0].model for call in provider.chat.await_args_list] == [
        selected.name, backup.name,
    ]
    assert all(
        call.args[0].max_tokens == 128 for call in provider.chat.await_args_list
    )
    assert [message["role"] for message in history.get("regression")] == [
        "user", "assistant",
    ]


@pytest.mark.asyncio
async def test_failed_refresh_preserves_models(monkeypatch):
    store = RegistryStorage()
    old = ModelMetadata(provider="ollama", name="old:3b")
    store.add(old)
    monkeypatch.setattr("app.registry.service.storage", store)
    provider = Mock()
    provider.list_model_details = AsyncMock(side_effect=RuntimeError("offline"))
    providers = Mock()
    providers.get.return_value = provider
    registry = RegistryService(providers)

    with pytest.raises(RuntimeError, match="offline"):
        await registry.refresh()
    assert registry.models() == [old]


@pytest.mark.asyncio
async def test_refresh_publishes_only_complete_snapshot(monkeypatch):
    store = RegistryStorage()
    old = ModelMetadata(provider="ollama", name="old:3b")
    new = ModelMetadata(provider="ollama", name="new:3b")
    store.add(old)
    monkeypatch.setattr("app.registry.service.storage", store)
    started = asyncio.Event()
    release = asyncio.Event()

    async def discover():
        started.set()
        await release.wait()
        return [new]

    provider = Mock()
    provider.list_model_details = discover
    providers = Mock()
    providers.get.return_value = provider
    registry = RegistryService(providers)
    task = asyncio.create_task(registry.refresh())
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert registry.models() == [old]
    finally:
        release.set()
        await task
    assert [model.name for model in registry.models()] == [new.name]


@pytest.mark.asyncio
async def test_invalid_refresh_preserves_entire_snapshot(monkeypatch):
    store = RegistryStorage()
    old = ModelMetadata(provider="ollama", name="old:3b")
    store.add(old)
    monkeypatch.setattr("app.registry.service.storage", store)
    valid = ModelMetadata(provider="ollama", name="new:3b")
    invalid = Mock()
    invalid.name = "invalid"
    invalid.capabilities = []
    invalid.parameter_size = "3B"
    invalid.context_length = "not an integer"
    provider = Mock()
    provider.list_model_details = AsyncMock(return_value=[valid, invalid])
    providers = Mock()
    providers.get.return_value = provider

    with pytest.raises(ValidationError):
        await RegistryService(providers).refresh()
    assert store.all() == [old]
