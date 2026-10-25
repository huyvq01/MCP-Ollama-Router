from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "openWorldHint": False,
        },
        auth=require_scopes("admin"),
    )
    def clear_cache() -> str:
        container.cache.clear()
        return "Cache cleared."
