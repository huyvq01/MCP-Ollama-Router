import pytest

from app.dependencies import container


@pytest.mark.asyncio
async def test_provider_registry_startup():
    registry = container.provider_registry

    await registry.startup()

    try:
        assert registry is not None
        assert len(registry.names()) > 0
    finally:
        await registry.shutdown()


@pytest.mark.asyncio
async def test_provider_registry_healthy():
    registry = container.provider_registry

    await registry.startup()

    try:
        healthy = await registry.healthy()

        assert isinstance(healthy, list)

        for provider_name in healthy:
            assert provider_name in registry.names()

    finally:
        await registry.shutdown()


@pytest.mark.asyncio
async def test_provider_models():
    registry = container.provider_registry

    await registry.startup()

    try:
        for name in registry.names():
            provider = registry.get(name)

            assert provider is not None

            models = await provider.list_models()

            assert isinstance(models, list)

    finally:
        await registry.shutdown()
