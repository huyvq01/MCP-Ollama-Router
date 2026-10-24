import pytest

from app.dependencies import container
from app.registry.schemas import ModelMetadata
from app.router.selector import ModelSelector


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_selector_select_model() -> None:
    provider_registry = container.provider_registry

    await provider_registry.startup()

    try:
        await container.registry.refresh()

        selector = ModelSelector(container.registry)

        selected = await selector.select("Write a Python web server.")

        assert isinstance(selected, ModelMetadata)

        assert selected.provider == "ollama"

        assert selected.name != ""

        assert "code" in selected.capabilities

    finally:
        await provider_registry.shutdown()
