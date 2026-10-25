from app.core.settings import settings
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.matcher import matcher


class ModelSelector:
    def __init__(self, registry: RegistryService) -> None:
        self._registry = registry

    async def select(self, prompt: str) -> ModelMetadata:
        capability = matcher.match(prompt).value
        models = self._registry.enabled()
        if not models:
            raise RuntimeError("No available model. Run: ollama pull qwen2.5-coder:3b")
        preferred = (
            settings.report_model if capability == "report" else settings.default_model
        )
        for model in models:
            if model.name == preferred:
                return model
        candidates = [m for m in models if capability in m.capabilities]
        if not candidates:
            candidates = [m for m in models if "general" in m.capabilities] or models
        return max(candidates, key=lambda m: (m.priority, m.name))
