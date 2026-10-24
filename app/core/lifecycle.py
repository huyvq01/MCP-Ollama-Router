import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from app.dependencies import container
from app.runtime import runtime


@asynccontextmanager
async def app_lifespan(
    server: FastMCP,
) -> AsyncIterator[dict[str, object]]:
    try:
        async with asyncio.timeout(runtime.startup_timeout_s):
            await container.provider_registry.startup()
            await container.registry.refresh()

        yield {}

    finally:
        await container.provider_registry.shutdown()
