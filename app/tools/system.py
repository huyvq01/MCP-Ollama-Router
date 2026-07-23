from fastmcp import FastMCP

from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool
    def clear_cache() -> str:
        container.cache.clear()
        return "Cache cleared."
