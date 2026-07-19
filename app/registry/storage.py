from app.registry.schemas import ModelMetadata


class ModelStorage:

    def __init__(self):

        self._models: dict[str, ModelMetadata] = {}

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

        return list(
            self._models.values()
        )

    def clear(self):

        self._models.clear()


storage = ModelStorage()