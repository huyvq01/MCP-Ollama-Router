from unittest.mock import Mock

import pytest

from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.selector import ModelSelector


@pytest.mark.asyncio
async def test_select_code():
    registry = Mock(spec=RegistryService)

    registry.enabled.return_value = [
        ModelMetadata(
            provider="ollama",
            name="coder",
            capabilities=["code"],
            priority=10,
        ),
        ModelMetadata(
            provider="ollama",
            name="general",
            capabilities=["general"],
            priority=50,
        ),
    ]

    selector = ModelSelector(registry)

    selected = await selector.select("write python code")

    assert selected.provider == "ollama"
    assert selected.name == "coder"
