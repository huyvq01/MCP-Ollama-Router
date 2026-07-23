from fastmcp import FastMCP

from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool
    async def health() -> dict[str, object]:
        healthy = await container.provider_registry.healthy()

        return {
            "providers": healthy,
            "count": len(healthy),
        }
