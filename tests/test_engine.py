import pytest

from app.dependencies import container


@pytest.mark.asyncio
async def test_engine_chat():
    provider_registry = container.provider_registry
    router = container.router

    await provider_registry.startup()

    try:
        await container.registry.refresh()

        answer = await router.chat(
            "demo",
            "Hello",
        )

        assert isinstance(answer, str)
        assert answer != ""

    finally:
        await provider_registry.shutdown()
