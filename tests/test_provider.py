import asyncio

from app.providers import provider_registry


async def main():

    await provider_registry.startup()

    print(
        provider_registry.names()
    )

    print(
        await provider_registry.healthy()
    )

    await provider_registry.shutdown()


if __name__ == "__main__":

    asyncio.run(main())