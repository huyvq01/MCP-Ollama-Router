from app.registry.schemas import ModelMetadata


class RegistryStorage:

    def __init__(self):

        self._models: dict[str, ModelMetadata] = {}

    def clear(self):

        self._models.clear()

    def add(
        self,
        model: ModelMetadata,
    ):

        self._models[model.name] = model

    def get(
        self,
        name: str,
    ):

        return self._models.get(name)

    def list(self):

        return list(self._models.values())

    def enabled(self):

        return [
            model
            for model in self._models.values()
            if model.enabled
        ]


storage = RegistryStorage()