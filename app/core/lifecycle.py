from app.dependencies import container


async def startup():

    await container.provider_registry.startup()

    if container.provider_registry.get("ollama") is None:
        raise RuntimeError(
            "Ollama provider is not registered."
        )

    await container.registry.refresh()


async def shutdown():

    await container.provider_registry.shutdown()