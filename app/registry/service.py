from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.storage import storage


class RegistryService:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
    ) -> None:
        self._provider_registry = provider_registry

    async def refresh(self) -> None:
        storage.clear()

        provider = self._provider_registry.get("ollama")

        if provider is None:
            raise RuntimeError("Provider 'ollama' is not registered.")

        models = await provider.list_models()

        for name in models:
            capabilities = ["general"]

            lower = name.lower()

            if "coder" in lower:
                capabilities.append("code")

            if "deepseek" in lower:
                capabilities.append("reasoning")

            if "llava" in lower:
                capabilities.append("vision")

            storage.add(
                ModelMetadata(
                    provider="ollama",
                    name=name,
                    capabilities=capabilities,
                )
            )

    def models(self) -> list[ModelMetadata]:
        return storage.all()

    def enabled(self) -> list[ModelMetadata]:
        return storage.enabled()

    def model(
        self,
        name: str,
    ) -> ModelMetadata | None:
        return storage.get(name)
