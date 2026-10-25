from fastmcp import FastMCP

from app.tools.chat import register as register_chat
from app.tools.health import register as register_health
from app.tools.models import register as register_models
from app.tools.system import register as register_system
from app.tools.workspace import register as register_workspace


def register_all(server: FastMCP) -> None:
    register_chat(server)
    register_models(server)
    register_health(server)
    register_system(server)
    register_workspace(server)
