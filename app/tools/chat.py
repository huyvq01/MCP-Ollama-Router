from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from app.config import MAX_REQUEST_OUTPUT_TOKENS
from app.dependencies import container


def register(server: FastMCP) -> None:
    @server.tool
    async def chat(
        session_id: str,
        prompt: str,
        model: str | None = None,
        max_tokens: Annotated[
            int | None, Field(ge=1, le=MAX_REQUEST_OUTPUT_TOKENS)
        ] = None,
    ) -> str:
        """Answer using local Ollama. Automatically choose the model, response
        style and output budget for code, explanations or documentation.
        Normally pass only session_id and prompt. Reuse session_id for follow-ups.
        Optional model and max_tokens override automatic choices.
        """
        if max_tokens is not None:
            return await container.router.chat(
                session_id=session_id,
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
            )
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
