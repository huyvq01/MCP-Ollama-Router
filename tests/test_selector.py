import asyncio

from app.providers import provider_registry
from app.router.selector import ModelSelector


async def main():

    await provider_registry.startup()

    selector = ModelSelector()

    provider, model = await selector.select(
        "Write a Python web server."
    )

    print(provider)
    print(model)

    await provider_registry.shutdown()


asyncio.run(main())