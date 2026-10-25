import json
import time
from unittest.mock import AsyncMock

import jwt
from pydantic import SecretStr
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.dependencies import container
from app.server import create_server
from app.services.workspace import Workspace


def parse(response):
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    lines = [
        line[6:] for line in response.text.splitlines() if line.startswith("data: ")
    ]
    return json.loads(lines[-1])


def make_token(config, subject="reader", scopes="chat repo:read", **overrides):
    now = int(time.time())
    claims = {
        "sub": subject,
        "client_id": subject,
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "iat": now,
        "exp": now + 600,
        "scope": scopes,
    }
    claims.update(overrides)
    return jwt.encode(claims, config.jwt_secret.get_secret_value(), algorithm="HS256")


def session(client, token):
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
    )
    assert response.status_code == 200, response.text
    session_id = response.headers.get("mcp-session-id")
    if session_id:
        headers["mcp-session-id"] = session_id
    headers["MCP-Protocol-Version"] = parse(response)["result"]["protocolVersion"]
    client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    return headers


def test_http_auth_scope_filter_and_denial(monkeypatch, tmp_path):
    monkeypatch.setattr(container, "workspace", Workspace(tmp_path))
    monkeypatch.setattr(container.registry, "refresh", AsyncMock())
    config = Settings(_env_file=None, transport="http", jwt_secret=SecretStr("z" * 48))
    app = create_server(config).http_app(
        path="/mcp",
        allowed_hosts=["testserver"],
        allowed_origins=[],
        stateless_http=True,
    )
    with TestClient(app) as client:
        assert client.post("/mcp").status_code == 401
        assert (
            client.post("/mcp", headers={"Authorization": "Bearer invalid"}).status_code
            == 401
        )
        reader = session(client, make_token(config))
        response = client.post(
            "/mcp",
            headers=reader,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        names = {tool["name"] for tool in parse(response)["result"]["tools"]}
        assert "read_file" in names
        assert "apply_changes" not in names
        assert "run_check" not in names
        denied = client.post(
            "/mcp",
            headers=reader,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "apply_changes", "arguments": {"plan_id": "a" * 32}},
            },
        )
        payload = parse(denied)
        assert "error" in payload or payload.get("result", {}).get("isError")
        writer = session(
            client, make_token(config, "writer", "chat repo:read repo:write repo:run")
        )
        response = client.post(
            "/mcp",
            headers=writer,
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
        )
        names = {tool["name"] for tool in parse(response)["result"]["tools"]}
        assert "apply_changes" in names and "run_check" in names
        assert "git_push" not in names


def test_expired_http_token_and_bad_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(container, "workspace", Workspace(tmp_path))
    monkeypatch.setattr(container.registry, "refresh", AsyncMock())
    config = Settings(_env_file=None, transport="http", jwt_secret=SecretStr("z" * 48))
    app = create_server(config).http_app(
        path="/mcp",
        allowed_hosts=["testserver"],
        allowed_origins=[],
        stateless_http=True,
    )
    with TestClient(app) as client:
        expired = make_token(config, exp=int(time.time()) - 2)
        assert (
            client.post(
                "/mcp", headers={"Authorization": "Bearer " + expired}
            ).status_code
            == 401
        )
        no_exp = jwt.encode(
            {"sub": "a", "aud": config.jwt_audience, "iss": config.jwt_issuer},
            config.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )
        assert (
            client.post(
                "/mcp", headers={"Authorization": "Bearer " + no_exp}
            ).status_code
            == 401
        )
        valid = make_token(config)
        bad = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer " + valid,
                "Origin": "https://evil.invalid",
            },
        )
        assert bad.status_code in {400, 403, 421}
