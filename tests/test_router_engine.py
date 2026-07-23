import asyncio

from app.dependencies import container


async def main():
    provider_registry = container.provider_registry
    router = container.router

    await provider_registry.startup()

    try:
        print(
            await router.chat(
                "demo",
                "Hello",
            )
        )

        print(
            await router.chat(
                "demo",
                "What did I ask before?",
            )
        )

        print(router.sessions())

    finally:
        await provider_registry.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
