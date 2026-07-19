import asyncio

from app.providers import provider_registry
from app.router import router_engine


async def main():

    await provider_registry.startup()

    print(
        await router_engine.chat(
            "demo",
            "Hello"
        )
    )

    await provider_registry.shutdown()


asyncio.run(main())