from app.providers import provider_registry
from app.registry.storage import storage
from app.registry.schemas import ModelMetadata


class RegistryService:

    async def refresh(self):

        storage.clear()

        provider = provider_registry.get("ollama")

        if provider is None:
            raise RuntimeError("Provider 'ollama' is not registered")

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

    def models(self):
        return storage.list()

    def model(self, name: str):
        return storage.get(name)


registry_service = RegistryService()