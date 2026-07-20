class FallbackManager:

    async def fallback(
        self,
        provider,
        model,
        messages,
    ):

        return await provider.chat(
            model=model,
            messages=messages,
        )