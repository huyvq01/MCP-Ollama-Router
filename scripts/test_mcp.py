import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(
        keep_alive=False,
        command=sys.executable,
        args=["-m", "app.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    async with Client(transport) as client:
        print([tool.name for tool in await client.list_tools()])
        print(
            await client.call_tool(
                "chat",
                {
                    "session_id": "smoke",
                    "prompt": "Write only a Java method adding two integers.",
                    "mode": "code",
                    "max_tokens": 96,
                },
            )
        )
        print(await client.call_tool("chat_metrics", {"session_id": "smoke"}))


if __name__ == "__main__":
    asyncio.run(main())
