from app.providers import provider_registry

from app.router.selector import ModelSelector
from app.router.fallback import FallbackManager

from app.router.context import context
from app.prompts.builder import builder


class RouterEngine:

    def __init__(self):

        self.selector = ModelSelector()

        self.fallback = FallbackManager()

    async def chat(
        self,
        session_id: str,
        prompt: str,
    ):

        provider_name, model = await self.selector.select(
            prompt
        )

        provider = provider_registry.get(
            provider_name
        )

        if provider is None:

            raise RuntimeError(
                f"Provider {provider_name} not found."
            )

        history = context.history.get(
            session_id
        )

        messages = builder.build(
            history,
            prompt,
        )

        answer = await provider.chat(
            model=model,
            messages=messages,
        )

        context.history.append(
            session_id,
            "user",
            prompt,
        )

        context.history.append(
            session_id,
            "assistant",
            answer,
        )

        return answer

    def clear(
        self,
        session_id,
    ):

        context.history.clear(session_id)

    def sessions(self):

        return context.history.sessions()


router = RouterEngine()