from fastmcp import FastMCP

from app.dependencies import container
from app.registry.schemas import ModelMetadata


def register(server: FastMCP) -> None:
    @server.tool
    def list_models() -> list[ModelMetadata]:
        return container.registry.models()

    @server.tool
    def show_model(
        model: str,
    ) -> ModelMetadata | None:
        return container.registry.model(model)
