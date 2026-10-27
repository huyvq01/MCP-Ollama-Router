from typing import Literal

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from app.dependencies import container
from app.security import identity, session_key


def register(server: FastMCP) -> None:
    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    async def chat(
        session_id: str,
        prompt: str,
        model: str | None = None,
        mode: Literal["auto", "code", "report"] = "auto",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Answer code questions or write reports using the local model router.
        Use mode=auto and omit model for automatic selection: the configured
        report model handles reports, the default model handles other questions.
        The user does not need to name tools or models. Use a new session_id for
        unrelated tasks and reuse it for follow-ups. For repository questions,
        locate/read the actual source first and include only relevant evidence.
        This tool generates text; it does not read or modify files itself."""
        return await container.router.chat(
            session_id=session_key(session_id),
            prompt=prompt,
            model=model,
            mode=mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    def chat_metrics(session_id: str) -> dict[str, object]:
        """Return timings, actual model, token counts and stop reason for the
        last completed request."""
        return container.router.metrics(session_key(session_id))

    @server.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    def clear_chat(session_id: str) -> str:
        container.router.clear(session_key(session_id))
        return "Conversation cleared."

    @server.tool(
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
        auth=require_scopes("chat"),
    )
    def list_sessions() -> list[str]:
        owner = identity()
        sessions = container.router.sessions()
        if owner == "local-stdio":
            return sessions
        prefix = owner[:32] + ":"
        return [s[len(prefix) :] for s in sessions if s.startswith(prefix)]
