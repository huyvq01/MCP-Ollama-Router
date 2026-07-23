import pytest_asyncio

from app.dependencies import container


@pytest_asyncio.fixture
async def provider_registry():
    registry = container.provider_registry

    await registry.startup()

    try:
        yield registry
    finally:
        await registry.shutdown()


@pytest_asyncio.fixture
async def registry(provider_registry):
    await container.registry.refresh()
    return container.registry


@pytest_asyncio.fixture
def router():
    return container.router


@pytest_asyncio.fixture
def history():
    return container.history


@pytest_asyncio.fixture
def cache():
    return container.cache


@pytest_asyncio.fixture
def session():
    return container.session
