from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.matcher import matcher


class ModelSelector:
    def __init__(
        self,
        registry: RegistryService,
    ) -> None:
        self._registry = registry

    async def select(
        self,
        prompt: str,
    ) -> ModelMetadata:
        capability = matcher.match(prompt).value

        models = self._registry.enabled()

        if not models:
            raise RuntimeError("No available model.")

        candidates = [model for model in models if capability in model.capabilities]

        if not candidates:
            candidates = [model for model in models if "general" in model.capabilities]

        if not candidates:
            candidates = models

        return max(
            candidates,
            key=lambda model: model.priority,
        )
