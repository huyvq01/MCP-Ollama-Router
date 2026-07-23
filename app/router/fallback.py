from app.registry.schemas import ModelMetadata


class FallbackManager:
    def next(
        self,
        current: ModelMetadata,
        candidates: list[ModelMetadata],
    ) -> ModelMetadata | None:
        ordered = sorted(
            candidates,
            key=lambda model: model.priority,
            reverse=True,
        )

        found = False

        for model in ordered:
            if found:
                return model

            if model.name == current.name:
                found = True

        return None
