from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.matcher import matcher
from app.router.policy import RoutingPolicy


class ModelSelector:
    def __init__(
        self,
        registry: RegistryService,
    ) -> None:
        self._registry = registry
        self.policy = RoutingPolicy()

    async def select(
        self,
        prompt: str,
    ) -> ModelMetadata:
        capability = matcher.match(prompt)
        complexity = matcher.complexity(prompt)

        models: list[ModelMetadata] = (
            self._registry.enabled()
        )

        if not models:
            raise RuntimeError(
                "No available model."
            )

        return max(
            models,
            key=lambda model: self.policy.score(
                model,
                capability,
                complexity,
            ),
        )