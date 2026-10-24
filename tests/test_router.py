import pytest

from app.dependencies import container


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_router_history():
    provider_registry = container.provider_registry
    router = container.router

    await provider_registry.startup()

    try:
        await container.registry.refresh()

        first = await router.chat("demo", "Hello")

        second = await router.chat("demo", "Who am I?")

        assert isinstance(first, str)
        assert isinstance(second, str)

        history = container.history.get("demo")

        assert len(history) >= 4

        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[3]["role"] == "assistant"

    finally:
        router.clear("demo")
        await provider_registry.shutdown()
