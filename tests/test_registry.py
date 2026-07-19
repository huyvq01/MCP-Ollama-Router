import asyncio

from app.core.lifecycle import startup
from app.core.lifecycle import shutdown

from app.registry import registry_service


async def main():

    await startup()

    for model in registry_service.models():

        print(model)

    await shutdown()


asyncio.run(main())