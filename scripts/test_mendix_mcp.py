"""Read-only live MCP + mx + Ollama smoke test, with isolated router state."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main(args):
    with tempfile.TemporaryDirectory(prefix="mendix-smoke-") as temporary:
        env = {
            "ROUTER_WORKSPACE_ROOT": temporary,
            "ROUTER_STATE_DIR": str(Path(temporary) / ".router-state"),
            "ROUTER_TRANSPORT": "stdio",
        }
        if args.project:
            env["ROUTER_MENDIX_PROJECT"] = args.project
        if args.mx:
            env["ROUTER_MENDIX_MX_EXECUTABLE"] = args.mx
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "app.server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
            keep_alive=False,
        )
        async with Client(transport) as client:

            async def call(name, **arguments):
                return (await client.call_tool(name, arguments)).data

            info = await call("mendix_info")
            print("MCP connected; configured project:", info["project"], flush=True)
            sources = await call("mendix_list_sources", limit=1)
            if sources["files"]:
                await call("mendix_read_source", path=sources["files"][0], end_line=10)
            export = await call("mendix_start_export", modules=args.module)
            last = None
            while True:
                status = await call(
                    "mendix_export_status", export_id=export["export_id"]
                )
                if status["status"] != last:
                    last = status["status"]
                    print("Export:", last, flush=True)
                if last in {"completed", "failed", "interrupted"}:
                    break
                await asyncio.sleep(2)
            if last != "completed":
                raise RuntimeError(status.get("error", last))
            units = await call(
                "mendix_list_units", export_id=export["export_id"], query=args.query
            )
            if units["total"] != 1:
                raise ValueError(
                    "Query must match exactly one unit: "
                    + json.dumps(units["units"], ensure_ascii=False)
                )
            unit = units["units"][0]
            await call(
                "mendix_read_unit", export_id=export["export_id"], unit_id=unit["id"]
            )
            report = await call(
                "mendix_start_report", export_id=export["export_id"], unit_id=unit["id"]
            )
            if report["total_chunks"] > args.max_steps:
                raise ValueError("Select a smaller unit or raise --max-steps")
            results = []
            for _ in range(report["total_chunks"]):
                step = await call("mendix_report_step", report_id=report["report_id"])
                if step["status"] == "retry_required":
                    raise RuntimeError(step["error"])
                results.extend(step["results"])
                print(f"Review: {step['processed']}/{step['total']}", flush=True)
            assert step["status"] == "completed"
            if args.output:
                text = [
                    f"# Báo cáo thử: {unit['name']}",
                    "",
                    "Nguồn: mô hình đã lưu của Mendix 11.6.3; "
                    "đọc qua MCP và xử lý bằng Ollama.",
                    "",
                    "Đây là nhận xét AI theo từng đoạn JSON; chưa xác minh "
                    "liên tài liệu, chưa build hoặc chạy ứng dụng.",
                    "",
                    f"Unit ID: `{unit['id']}`",
                    "",
                ]
                for result in results:
                    text += [
                        f"## Đoạn {result['chunk'] + 1} — JSON dòng "
                        f"{result['start_line']}–{result['end_line']}",
                        "",
                        result["review"],
                        "",
                    ]
                    if result.get("warning"):
                        text += ["**Đầu ra bị cắt do giới hạn token.**", ""]
                output = Path(args.output).resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("\n".join(text), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "counts": status["counts"],
                        "unit": unit["name"],
                        "chunks": len(results),
                        "models": sorted(
                            {r["metrics"].get("model", "") for r in results}
                        ),
                        "truncated_chunks": sum(
                            bool(r.get("warning")) for r in results
                        ),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="AMS")
    parser.add_argument("--query", default="AMS.ACT_LiquidationAsset_ShowDetail")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--project")
    parser.add_argument("--mx")
    parser.add_argument("--output")
    asyncio.run(main(parser.parse_args()))
