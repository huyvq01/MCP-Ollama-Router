from unittest.mock import AsyncMock, Mock

import pytest

from app.models.provider import ModelInfo
from app.providers.registry import ProviderRegistry
from app.registry.service import RegistryService


@pytest.mark.asyncio
async def test_refresh():
    provider = AsyncMock()

    provider.list_model_details.return_value = [
        ModelInfo(
            provider="ollama",
            name="qwen2.5-coder:7b",
            family="qwen2",
            parameter_size="7.6B",
            quantization="Q4_K_M",
            capabilities=[
                "completion",
                "tools",
                "insert",
            ],
        ),
        ModelInfo(
            provider="ollama",
            name="deepseek-r1:14b",
            family="deepseek",
            parameter_size="14B",
            quantization="Q4_K_M",
            capabilities=[
                "completion",
                "thinking",
            ],
        ),
    ]

    provider_registry = Mock(
        spec=ProviderRegistry,
    )

    provider_registry.get.return_value = provider

    registry = RegistryService(
        provider_registry,
    )

    await registry.refresh()

    models = registry.models()

    assert len(models) == 2

    coder = registry.model(
        "qwen2.5-coder:7b",
    )

    assert coder is not None
    assert coder.provider == "ollama"
    assert "code" in coder.capabilities

    reasoning = registry.model(
        "deepseek-r1:14b",
    )

    assert reasoning is not None
    assert reasoning.provider == "ollama"
    assert "reasoning" in reasoning.capabilities