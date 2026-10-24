import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.lifecycle import app_lifespan
from app.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_native_tool_capabilities_discovered_without_inference():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{
                "name": "coder:3b", "details": {"parameter_size": "3B"},
            }]})
        assert request.url.path == "/api/show"
        assert json.loads(request.content) == {"model": "coder:3b"}
        return httpx.Response(200, json={
            "capabilities": ["completion", "tools"],
            "model_info": {"qwen.context_length": 32768},
        })
    provider = OllamaProvider()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider.client = client
        models = await provider.list_model_details()
    assert models[0].capabilities == ["completion", "tools"]
    assert models[0].context_length == 32768
    assert paths == ["/api/tags", "/api/show"]


@pytest.mark.asyncio
async def test_lifespan_cleans_up_after_startup_failure(monkeypatch):
    import app.core.lifecycle as module
    providers = SimpleNamespace(startup=AsyncMock(), shutdown=AsyncMock())
    registry = SimpleNamespace(refresh=AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr(module, "container", SimpleNamespace(provider_registry=providers, registry=registry))
    with pytest.raises(RuntimeError, match="offline"):
        async with app_lifespan(None):
            pass
    providers.shutdown.assert_awaited_once()
