"""Start an authenticated loopback HTTP server and check scoped MCP access."""

import asyncio
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import jwt
from fastmcp import Client


async def main():
    project = Path(__file__).resolve().parents[1]
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    secret = secrets.token_urlsafe(48)
    now = int(time.time())

    def token(subject, scopes):
        return jwt.encode(
            {
                "sub": subject,
                "client_id": subject,
                "iss": "mcp-ollama-router",
                "aud": "mcp-ollama-router",
                "iat": now,
                "exp": now + 300,
                "scope": scopes,
            },
            secret,
            algorithm="HS256",
        )

    with tempfile.TemporaryDirectory(prefix="router-http-") as folder:
        root = Path(folder)
        (root / "example.py").write_text("value = 1\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            ROUTER_WORKSPACE_ROOT=str(root),
            ROUTER_STATE_DIR=str(root / ".router-state"),
            ROUTER_JWT_SECRET=secret,
            ROUTER_TRANSPORT="stdio",
            ROUTER_JWT_JWKS_URI="",
            ROUTER_HTTP_PUBLIC_URL=f"http://127.0.0.1:{port}",
        )
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "app.server",
                    "--transport",
                    "http",
                    "--port",
                    str(port),
                ],
                cwd=project,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
            try:
                url = f"http://127.0.0.1:{port}/mcp"
                async with httpx.AsyncClient(trust_env=False, timeout=2) as http:
                    for _ in range(100):
                        if proc.poll() is not None:
                            log.seek(0)
                            raise RuntimeError(
                                log.read().decode(errors="replace")[-4000:]
                            )
                        try:
                            response = await http.post(url)
                            if response.status_code == 401:
                                break
                        except httpx.TransportError:
                            pass
                        await asyncio.sleep(0.1)
                    else:
                        raise RuntimeError("HTTP server did not become ready")
                    assert (
                        await http.post(
                            url, headers={"Authorization": "Bearer invalid"}
                        )
                    ).status_code == 401
                print("PASS HTTP rejects missing/invalid bearer token", flush=True)
                async with Client(
                    url, auth=token("reader", "chat repo:read")
                ) as reader:
                    names = {tool.name for tool in await reader.list_tools()}
                    assert "read_file" in names and "apply_changes" not in names
                    result = await reader.call_tool("read_file", {"path": "example.py"})
                    assert result.data["content"] == "value = 1"
                    print("PASS read-only scope and remote file read", flush=True)
                async with Client(
                    url, auth=token("writer", "chat repo:read repo:write")
                ) as writer:
                    plan = (
                        await writer.call_tool(
                            "propose_changes",
                            {
                                "changes": [
                                    {"path": "example.py", "content": "value = 2\n"}
                                ]
                            },
                        )
                    ).data
                    identifier = plan["plan_id"]
                    await writer.call_tool("apply_changes", {"plan_id": identifier})
                    assert (root / "example.py").read_text() == "value = 2\n"
                    await writer.call_tool("rollback_changes", {"plan_id": identifier})
                    print("PASS authenticated apply/rollback", flush=True)
                async with Client(url, auth=token("other", "repo:write")) as other:
                    denied = await other.call_tool(
                        "change_status", {"plan_id": identifier}, raise_on_error=False
                    )
                    assert denied.is_error
                    print("PASS operation ownership isolation", flush=True)
                print(
                    "ALL HTTP MCP CHECKS PASSED; temporary server will stop.",
                    flush=True,
                )
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == "__main__":
    asyncio.run(main())
