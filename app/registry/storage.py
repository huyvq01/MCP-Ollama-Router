from app.registry.schemas import ModelMetadata


class RegistryStorage:
    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}

    def clear(self) -> None:
        self._models.clear()

    def replace(self, models: list[ModelMetadata]) -> None:
        """Publish a complete snapshot after all models are validated."""
        self._models = {model.name: model for model in models}

    def add(
        self,
        model: ModelMetadata,
    ) -> None:
        self._models[model.name] = model

    def get(
        self,
        name: str,
    ) -> ModelMetadata | None:
        return self._models.get(name)

    def all(self) -> list[ModelMetadata]:
        return list(self._models.values())

    def enabled(self) -> list[ModelMetadata]:
        return [model for model in self._models.values() if model.enabled]


storage = RegistryStorage()
