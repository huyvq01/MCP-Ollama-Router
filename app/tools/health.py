from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    async def health() -> dict[str, object]:
        healthy = await container.provider_registry.healthy()

        return {
            "providers": healthy,
            "count": len(healthy),
        }
