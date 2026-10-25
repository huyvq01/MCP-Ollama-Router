"""Run stdio locally, or authenticated Streamable HTTP."""

import argparse

from fastmcp import FastMCP

from app.core.lifecycle import app_lifespan
from app.core.settings import settings
from app.security import build_auth
from app.tools import register_all


def create_server(config=settings) -> FastMCP:
    result = FastMCP(
        "AI Router",
        version=config.version,
        lifespan=app_lifespan,
        auth=build_auth(config),
    )
    register_all(result)
    return result


server = create_server()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"])
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = settings.model_copy(
        update={
            k: v
            for k, v in {
                "transport": args.transport,
                "http_host": args.host,
                "http_port": args.port,
            }.items()
            if v is not None
        }
    )
    instance = create_server(config)
    if config.transport == "stdio":
        instance.run(show_banner=False)
    else:
        instance.run(
            transport="http",
            host=config.http_host,
            port=config.http_port,
            path="/mcp",
            show_banner=False,
            allowed_hosts=config.http_allowed_hosts,
            allowed_origins=config.http_allowed_origins,
        )


if __name__ == "__main__":
    main()
