import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP

from app.dependencies import container


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, object]]:
    container.workspace.acquire_server()
    try:
        await container.provider_registry.startup()
        try:
            await container.registry.refresh()
        except (httpx.HTTPError, RuntimeError) as exc:
            logging.getLogger(__name__).warning(
                "Ollama unavailable at startup: %s", type(exc).__name__
            )
        yield {}
    finally:
        try:
            await container.mendix.shutdown()
            await container.provider_registry.shutdown()
        finally:
            container.workspace.release_server()
