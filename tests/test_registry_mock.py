from unittest.mock import AsyncMock, Mock

import pytest

from app.providers.registry import ProviderRegistry
from app.registry.service import RegistryService


@pytest.mark.asyncio
async def test_refresh():
    provider = AsyncMock()

    provider.list_models.return_value = [
        "qwen2.5-coder:7b",
        "deepseek-r1:14b",
    ]

    provider_registry = Mock(spec=ProviderRegistry)
    provider_registry.get.return_value = provider

    registry = RegistryService(provider_registry)

    await registry.refresh()

    models = registry.models()

    assert len(models) == 2
    assert models[0].provider == "ollama"
