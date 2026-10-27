from fastmcp import FastMCP

from app import server as server_module


def test_server_exists() -> None:
    assert isinstance(
        server_module.server,
        FastMCP,
    )


def test_server_name() -> None:
    assert server_module.server.name == "AI Router"


def test_coding_mode_exposes_router_tools(monkeypatch):
    from unittest.mock import Mock

    instance = Mock()
    monkeypatch.setattr(server_module, "create_server", lambda config: instance)
    monkeypatch.setattr(
        "sys.argv", ["server", "--coding-tools", "--transport", "stdio"]
    )
    server_module.main()
    options = instance.enable.call_args.kwargs
    assert {
        "chat",
        "chat_metrics",
        "list_models",
        "refresh_models",
        "read_file",
    } <= options["names"]
    assert "git_push" not in options["names"]
    assert options["only"] is True
    instance.run.assert_called_once_with(show_banner=False)
