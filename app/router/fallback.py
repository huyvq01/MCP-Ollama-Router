class FallbackManager:

    async def run(
        self,
        func,
        *args,
        **kwargs,
    ):

        return await func(
            *args,
            **kwargs,
        )