from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from app.dependencies import container
from app.registry.schemas import ModelMetadata


def register(server: FastMCP) -> None:
    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    def list_models() -> list[ModelMetadata]:
        return container.registry.models()

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    def show_model(
        model: str,
    ) -> ModelMetadata | None:
        return container.registry.model(model)

    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    async def refresh_models() -> list[ModelMetadata]:
        """Refresh installed Ollama models after downloading a model, without
        restarting MCP."""
        await container.registry.refresh()
        return container.registry.models()
