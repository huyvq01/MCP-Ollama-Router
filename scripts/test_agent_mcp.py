"""End-to-end agent tool checks in an isolated temporary workspace."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main():
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="router-smoke-") as directory:
        root = Path(directory)
        (root / "hello.py").write_text("value = 1\n", encoding="utf-8")
        env = {
            "ROUTER_WORKSPACE_ROOT": str(root),
            "ROUTER_TRANSPORT": "stdio",
            "ROUTER_STATE_DIR": str(root / ".router-state"),
            "ROUTER_CHECK_COMMANDS": json.dumps(
                {"smoke": ["{python}", "-c", 'print("CHECK_OK")']}
            ),
        }
        transport = StdioTransport(
            keep_alive=False,
            command=sys.executable,
            args=["-m", "app.server"],
            cwd=str(project),
            env=env,
        )
        async with Client(transport) as client:

            async def call(name, arguments=None):
                result = await client.call_tool(name, arguments or {})
                return result.data

            tools = await client.list_tools()
            print(f"MCP CONNECTED: {len(tools)} tools", flush=True)
            files = await call("list_files", {"include": "*.py"})
            assert "hello.py" in files["files"]
            assert (await call("read_file", {"path": "hello.py"}))[
                "content"
            ] == "value = 1"
            assert (await call("search_code", {"query": "value"}))["matches"]
            print("PASS list/read/search", flush=True)
            plan = await call(
                "propose_changes",
                {"changes": [{"path": "hello.py", "content": "value = 2\n"}]},
            )
            assert (root / "hello.py").read_text() == "value = 1\n"
            print("DIFF:", plan["diff"], flush=True)
            assert (await call("apply_changes", {"plan_id": plan["plan_id"]}))[
                "status"
            ] == "applied"
            assert (root / "hello.py").read_text() == "value = 2\n"
            assert (await call("run_check", {"name": "smoke"}))["exit_code"] == 0
            assert (await call("rollback_changes", {"plan_id": plan["plan_id"]}))[
                "status"
            ] == "rolled_back"
            assert (root / "hello.py").read_text() == "value = 1\n"
            print("PASS propose/apply/check/rollback", flush=True)
            job = await call("start_repository_scan", {"include": "hello.py"})
            result = await call("scan_repository", {"scan_id": job["scan_id"]})
            if result["status"] == "retry_required":
                raise RuntimeError("Ollama scan failed: " + result["error"])
            assert result["status"] == "completed"
            print("PASS repository scan:", result["result"]["review"], flush=True)
            print(
                "ALL AGENT MCP CHECKS PASSED; real source was not modified.", flush=True
            )


if __name__ == "__main__":
    asyncio.run(main())
