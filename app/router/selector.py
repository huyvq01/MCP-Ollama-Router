from app.registry import registry_service

from app.router.matcher import matcher
from app.router.policy import RoutingPolicy


class ModelSelector:

    def __init__(self):

        self.policy = RoutingPolicy()

    async def select(
        self,
        prompt: str,
    ):

        capability = matcher.capability(prompt)

        models = registry_service.enabled()

        if not models:

            raise RuntimeError(
                "No available model."
            )

        ranked = sorted(
            models,
            key=lambda m: self.policy.score(
                m,
                capability,
            ),
            reverse=True,
        )

        best = ranked[0]

        return (
            best.provider,
            best.name,
        )