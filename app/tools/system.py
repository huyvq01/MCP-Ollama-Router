from fastmcp import FastMCP

from app.services import cache


def register(server: FastMCP):

    @server.tool
    def clear_cache():

        cache.clear()

        return "Cache cleared."