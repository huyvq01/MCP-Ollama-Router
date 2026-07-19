import asyncio

from fastmcp import FastMCP

from app.core.lifecycle import startup
from app.core.lifecycle import shutdown

from app.tools import register_all

server = FastMCP(
    "AI Router"
)

register_all(server)


async def main():

    await startup()

    try:

        server.run()

    finally:

        await shutdown()


if __name__ == "__main__":

    asyncio.run(main())