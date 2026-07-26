import asyncio

from app.dependencies import container


async def main() -> None:
    await container.provider_registry.startup()

    try:
        print("Refreshing Ollama models...")
        await container.registry.refresh()

        print("\nAvailable models:")
        for model in container.registry.models():
            print(
                f"- {model.name} "
                f"[{', '.join(model.capabilities)}] "
                f"priority={model.priority}"
            )

        model_name = "qwen2.5-coder:3b"

        print(f"\nUsing model: {model_name}")
        print("Sending prompt...")

        answer = await container.router.chat(
            session_id="manual-test",
            prompt="Write a simple Python function that adds two numbers.",
            model=model_name,
        )

        print("\n=== RESPONSE ===")
        print(answer)

    finally:
        await container.provider_registry.shutdown()


if __name__ == "__main__":
    asyncio.run(main())