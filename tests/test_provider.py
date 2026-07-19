import asyncio

from app.providers import provider_registry


async def main():

    await provider_registry.startup()

    provider = provider_registry.get(
        "ollama"
    )

    print(
        await provider.health()
    )

    print(
        await provider.list_models()
    )

    print(
        await provider.chat(
            model="qwen2.5-coder:7b",
            messages=[
                {
                    "role": "user",
                    "content": "Hello"
                }
            ]
        )
    )

    await provider_registry.shutdown()


if __name__ == "__main__":

    asyncio.run(main())