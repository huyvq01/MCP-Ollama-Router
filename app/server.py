from fastmcp import FastMCP

from app.core.lifecycle import app_lifespan
from app.tools import register_all

server = FastMCP(
    "AI Router",
    lifespan=app_lifespan,
)

register_all(server)

if __name__ == "__main__":
    server.run()
