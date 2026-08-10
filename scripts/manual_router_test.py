import asyncio

from app.dependencies import container
from app.prompts.builder import builder
from app.services.token_budget import estimate_message_tokens


async def main() -> None:
    await container.provider_registry.startup()

    try:
        await container.registry.refresh()

        print("=== MODELS ===")

        for model in container.registry.models():
            print(
                model.name,
                model.capabilities,
                "priority=",
                model.priority,
            )

        print()
        print("=== BUILD CONTEXT ===")

        history = container.history.get(
            "manual-test"
        )

        messages = builder.build(
            history=history,
            prompt="Reply with exactly: OK",
        )

        total_tokens = sum(
            estimate_message_tokens(message)
            for message in messages
        )

        print(
            "messages =",
            len(messages),
        )

        print(
            "estimated input tokens =",
            total_tokens,
        )

        print()
        print("=== CHAT ===")

        result = await container.router.chat(
            session_id="manual-test",
            prompt="Reply with exactly: OK",
            model="qwen2.5-coder:3b",
        )

        print()
        print("=== RESULT ===")
        print(result)

    finally:
        await container.provider_registry.shutdown()


if __name__ == "__main__":
    asyncio.run(main())