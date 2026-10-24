from fastmcp import FastMCP

from app.config import MAX_ROUTER_MODEL_B
from app.dependencies import container
from app.router.model_size import supported
from app.router.tasks import analyze


def register(server: FastMCP) -> None:
    @server.tool
    def route_preview(prompt: str, session_id: str | None = None) -> dict[str, object]:
        """Preview task, chosen model and token budget without running inference."""
        history = container.history.get(session_id) if session_id is not None else []
        profile = analyze(prompt, history)
        candidates = container.router.selector.rank(profile.routing_prompt)
        return {
            "task": profile.task.value,
            "complexity": profile.complexity.value,
            "selected_model": candidates[0].name if candidates else None,
            "fallback_models": [model.name for model in candidates[1:]],
            "max_tokens": profile.max_tokens,
            "temperature": profile.temperature,
            "max_model_billions": MAX_ROUTER_MODEL_B,
            "excluded_models": [
                model.name for model in container.registry.enabled()
                if not supported(model)
            ],
            "strategy": "Local task rules, capability matching and model size",
        }
