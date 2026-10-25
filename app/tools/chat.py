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
        """Ask the local Java/Mendix assistant. Default: fast 3B model, concise
        output (512 tokens). Use mode=report for Vietnamese reports, code for
        implementation; split long reports into sections. Pass only relevant
        excerpts, not whole repositories. Reuse session_id for follow-ups; use
        a new one for unrelated work. 7B is slower and should be explicitly
        requested. This is a text assistant, not a file editor or web search
        tool."""
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
