from fastmcp import FastMCP

from app import server as server_module


def test_server_exists() -> None:
    assert isinstance(
        server_module.server,
        FastMCP,
    )


def test_server_name() -> None:
    assert server_module.server.name == "AI Router"
