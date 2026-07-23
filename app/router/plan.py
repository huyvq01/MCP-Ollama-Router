from app.registry.schemas import ModelMetadata


class RoutingPlan:
    def __init__(
        self,
        models: list[ModelMetadata],
    ) -> None:
        self._models = models
        self._index = 0

    def current(self) -> ModelMetadata | None:
        if self._index >= len(self._models):
            return None

        return self._models[self._index]

    def next(self) -> ModelMetadata | None:
        self._index += 1
        return self.current()

    def remaining(self) -> int:
        return max(
            0,
            len(self._models) - self._index,
        )
