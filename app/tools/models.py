from fastmcp import FastMCP

from app.services import client


def register(server: FastMCP):

    @server.tool
    def list_models():

        return client.list_models()

    @server.tool
    def show_model(
        model: str,
    ):

        return client.show_model(model)