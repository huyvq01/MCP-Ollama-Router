import asyncio

from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.storage import storage


class RegistryService:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
    ) -> None:
        self._provider_registry = provider_registry
        self._refresh_lock = asyncio.Lock()

    async def refresh(self) -> None:
        async with self._refresh_lock:
            await self._refresh()

    async def _refresh(self) -> None:
        provider = self._provider_registry.get(
            "ollama",
        )

        if provider is None:
            raise RuntimeError(
                "Provider 'ollama' is not registered."
            )

        models = await provider.list_model_details()
        snapshot: list[ModelMetadata] = []

        for model in models:
            capabilities = self._map_capabilities(
                model.name,
                model.capabilities,
            )

            snapshot.append(
                ModelMetadata(
                    provider=model.provider,
                    name=model.name,
                    family=model.family,
                    parameter_size=model.parameter_size,
                    quantization=model.quantization,
                    context_length=model.context_length,
                    capabilities=capabilities,
                    priority=self._priority(
                        model.parameter_size,
                    ),
                    enabled=model.enabled,
                )
            )

        storage.replace(snapshot)

    @staticmethod
    def _map_capabilities(
        model_name: str,
        provider_capabilities: list[str],
    ) -> list[str]:
        capabilities: list[str] = [
            "general",
        ]
        capabilities.extend(
            item for item in ("tools", "thinking", "embedding")
            if item in provider_capabilities
        )

        lower_name = model_name.lower()

        if (
            "coder" in lower_name
            or "code" in lower_name
            or "insert" in provider_capabilities
        ):
            capabilities.append("code")

        if (
            "deepseek" in lower_name
            or "reasoning" in lower_name
            or "thinking" in provider_capabilities
        ):
            capabilities.append("reasoning")

        if (
            "llava" in lower_name
            or "vision" in provider_capabilities
        ):
            capabilities.append("vision")

        return capabilities

    @staticmethod
    def _priority(
        parameter_size: str,
    ) -> int:
        normalized = parameter_size.upper().strip()

        try:
            value = float(
                normalized.rstrip("B"),
            )
        except ValueError:
            return 100

        if value <= 4:
            return 120

        if value <= 8:
            return 100

        if value <= 14:
            return 80

        return 60

    @staticmethod
    def _priority_from_name(
        model_name: str,
    ) -> int:
        lower = model_name.lower()

        if "3b" in lower:
            return 120

        if "7b" in lower:
            return 100

        if "14b" in lower:
            return 80

        return 100

    def models(self) -> list[ModelMetadata]:
        return storage.all()

    def enabled(self) -> list[ModelMetadata]:
        return storage.enabled()

    def model(
        self,
        name: str,
    ) -> ModelMetadata | None:
        return storage.get(name)
