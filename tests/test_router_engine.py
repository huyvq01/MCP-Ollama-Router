import asyncio

from app.providers import provider_registry
from app.router import router


async def main():

    await provider_registry.startup()

    print(
        await router.chat(
            "demo",
            "Hello"
        )
    )

    print(
        await router.chat(
            "demo",
            "What did I ask before?"
        )
    )

    print(
        router.sessions()
    )

    await provider_registry.shutdown()


asyncio.run(main())