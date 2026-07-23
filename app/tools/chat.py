from fastmcp import FastMCP

from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool
    async def chat(
        session_id: str,
        prompt: str,
        model: str | None = None,
    ) -> str:
        return await container.router.chat(
            session_id=session_id,
            prompt=prompt,
            model=model,
        )

    @server.tool
    def clear_chat(
        session_id: str,
    ) -> str:
        container.router.clear(session_id)
        return "Conversation cleared."

    @server.tool
    def list_sessions() -> list[str]:
        return container.router.sessions()
