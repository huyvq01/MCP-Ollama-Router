from fastmcp import FastMCP

from app.router.engine import router


def register(server: FastMCP):

    @server.tool
    async def chat(
        session_id: str,
        prompt: str,
    ) -> str:

        return await router.chat(
            session_id=session_id,
            prompt=prompt,
        )

    @server.tool
    def clear_chat(
        session_id: str,
    ) -> str:

        router.clear(session_id)

        return "Conversation cleared."

    @server.tool
    def list_sessions():

        return router.sessions()