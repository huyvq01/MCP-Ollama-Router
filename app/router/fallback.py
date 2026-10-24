from app.registry.schemas import ModelMetadata


class FallbackManager:
    def next(
        self,
        current: ModelMetadata,
        candidates: list[ModelMetadata],
    ) -> ModelMetadata | None:
        found = False

        # The engine already orders candidates by suitability and puts
        # the selected model first. Re-sorting here can skip valid models.
        for model in candidates:
            if found:
                return model

            if model.name == current.name:
                found = True

        return None
