import asyncio

from app.providers import provider_registry
from app.registry import registry_service


async def main():

    await provider_registry.startup()

    await registry_service.refresh()

    print(
        registry_service.models()
    )

    print(
        registry_service.enabled()
    )

    await provider_registry.shutdown()


if __name__ == "__main__":

    asyncio.run(main())