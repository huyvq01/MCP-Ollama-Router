import asyncio
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "app.server"],
        cwd=r"E:\MCP-Ollama-Router",
    )

    async with Client(transport) as client:
        print("=== MCP CONNECTED ===")

        print("\n=== TOOLS ===")
        tools = await client.list_tools()

        for tool in tools:
            print(f"- {tool.name}")

        print("\n=== LIST MODELS ===")
        models = await client.call_tool(
            "list_models",
            {},
        )
        print(models)

        print("\n=== CHAT ===")
        result = await client.call_tool(
            "chat",
            {
                "session_id": "direct-mcp-test",
                "prompt": "Reply with exactly: OK",
                "model": "qwen2.5-coder:3b",
            },
        )

        print("\n=== RESULT ===")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())