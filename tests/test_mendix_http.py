from unittest.mock import AsyncMock

from pydantic import SecretStr
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.dependencies import container
from app.server import create_server
from app.services.workspace import Workspace
from tests.test_http_agent import make_token, parse, session


def test_mendix_http_scope_visibility_and_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(container, "workspace", Workspace(tmp_path))
    monkeypatch.setattr(container.registry, "refresh", AsyncMock())
    start = AsyncMock(return_value={"export_id": "test"})
    monkeypatch.setattr(container.mendix, "start_export", start)
    config = Settings(_env_file=None, transport="http", jwt_secret=SecretStr("x" * 48))
    app = create_server(config).http_app(
        path="/mcp",
        allowed_hosts=["testserver"],
        stateless_http=True,
    )
    with TestClient(app) as client:
        reader = session(client, make_token(config, scopes="repo:read"))
        response = client.post(
            "/mcp",
            headers=reader,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            },
        )
        names = {tool["name"] for tool in parse(response)["result"]["tools"]}
        assert "mendix_read_unit" in names
        assert "mendix_start_export" not in names
        assert "mendix_start_report" not in names
        denied = client.post(
            "/mcp",
            headers=reader,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "mendix_start_export",
                    "arguments": {"modules": "AMS"},
                },
            },
        )
        assert "error" in parse(denied) or parse(denied).get("result", {}).get(
            "isError"
        )
        start.assert_not_called()
        runner = session(client, make_token(config, scopes="repo:read repo:run"))
        allowed = client.post(
            "/mcp",
            headers=runner,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "mendix_start_export",
                    "arguments": {"modules": "AMS"},
                },
            },
        )
        assert not parse(allowed)["result"].get("isError")
        start.assert_awaited_once()
