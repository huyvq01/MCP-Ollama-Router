from fastmcp import FastMCP

from app.services import client


def register(server: FastMCP):

    @server.tool
    def health():

        return client.health()