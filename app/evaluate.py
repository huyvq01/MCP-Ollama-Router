"""Synthetic routing checks and opt-in live latency measurements; never executes model code."""
import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

import httpx

from app.router.tasks import analyze
from app.runtime import runtime


async def evaluate(live: bool, limit: int, include_answers: bool) -> dict:
    cases = json.loads(Path(__file__).with_name("eval_cases.json").read_text(encoding="utf-8"))
    results = []
    if live and runtime.gateway_api_key is None:
        raise ValueError("Configure ROUTER_GATEWAY_API_KEY before running --live")
    headers = {"Authorization": "Bearer " + runtime.gateway_api_key.get_secret_value()} if live else {}
    async with httpx.AsyncClient(
        timeout=runtime.request_timeout_s + 10, trust_env=False,
    ) as client:
        for case in cases[:limit]:
            profile = analyze(case["prompt"])
            row = {"id": case["id"], "task": profile.task.value,
                   "routing_pass": profile.task.value == case["task"]}
            if live:
                start = perf_counter()
                first = None
                answer = ""
                try:
                    async with client.stream(
                        "POST", f"http://{runtime.gateway_host}:{runtime.gateway_port}/v1/chat/completions",
                        headers=headers, json={"model": "auto", "messages": [
                            {"role": "user", "content": case["prompt"]},
                        ], "max_tokens": 128, "stream": True,
                            "stream_options": {"include_usage": True}},
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data: ") or line == "data: [DONE]":
                                continue
                            event = json.loads(line[6:])
                            if "error" in event:
                                raise RuntimeError("Gateway stream reported an error")
                            row["model"] = event.get("model")
                            for choice in event.get("choices", []):
                                content = choice.get("delta", {}).get("content", "")
                                if content and first is None:
                                    first = perf_counter() - start
                                answer += content
                                if choice.get("finish_reason"):
                                    row["finish_reason"] = choice["finish_reason"]
                            if "usage" in event:
                                row["usage"] = event["usage"]
                    row.update({"live_pass": bool(answer), "first_content_s": first,
                                "total_s": perf_counter() - start})
                    if include_answers:
                        row["answer"] = answer
                except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                    row.update({"live_pass": False, "error_type": type(exc).__name__,
                                "total_s": perf_counter() - start})
            results.append(row)
    return {"mode": "live-synthetic" if live else "offline-routing", "results": results,
            "routing_passed": sum(item["routing_pass"] for item in results),
            "total": len(results), "note": "Routing checks and latency are not semantic quality guarantees."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=13)
    parser.add_argument("--include-answers", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("evaluation.json"))
    args = parser.parse_args()
    if not 1 <= args.limit <= 13:
        parser.error("--limit must be between 1 and 13")
    report = asyncio.run(evaluate(args.live, args.limit, args.include_answers))
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Routing: {report['routing_passed']}/{report['total']}; report: {args.out}")
    if any(not row["routing_pass"] or row.get("live_pass") is False for row in report["results"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
