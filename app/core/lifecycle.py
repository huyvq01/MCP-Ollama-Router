from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from app.dependencies import container


@asynccontextmanager
async def app_lifespan(
    server: FastMCP,
) -> AsyncIterator[dict[str, object]]:
    await container.provider_registry.startup()

    try:
        await container.registry.refresh()

        yield {}

    finally:
        await container.provider_registry.shutdown()
