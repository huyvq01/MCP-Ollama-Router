from app.providers import provider_registry
from app.registry import registry_service


async def startup():

    await provider_registry.startup()

    if provider_registry.get("ollama") is None:
        raise RuntimeError("Ollama provider is not registered.")

    await registry_service.refresh()


async def shutdown():

    await provider_registry.shutdown()