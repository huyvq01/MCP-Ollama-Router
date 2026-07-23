import pytest

from app.dependencies import container


@pytest.mark.asyncio
async def test_registry_refresh():
    provider_registry = container.provider_registry
    registry = container.registry

    await provider_registry.startup()

    try:
        await registry.refresh()

        models = registry.models()

        assert isinstance(models, list)
        assert len(models) > 0

    finally:
        await provider_registry.shutdown()


@pytest.mark.asyncio
async def test_registry_enabled():
    provider_registry = container.provider_registry
    registry = container.registry

    await provider_registry.startup()

    try:
        await registry.refresh()

        enabled = registry.enabled()

        assert isinstance(enabled, list)

        for model in enabled:
            assert model.enabled

    finally:
        await provider_registry.shutdown()


@pytest.mark.asyncio
async def test_registry_lookup():
    provider_registry = container.provider_registry
    registry = container.registry

    await provider_registry.startup()

    try:
        await registry.refresh()

        models = registry.models()

        if models:
            model = registry.model(models[0].name)

            assert model is not None
            assert model.name == models[0].name

    finally:
        await provider_registry.shutdown()
