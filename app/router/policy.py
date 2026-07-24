from app.registry.schemas import ModelMetadata


class RoutingPolicy:
    def score(
        self,
        model: ModelMetadata,
        capability: str,
    ) -> int:
        score = model.priority

        if capability in model.capabilities:
            score += 100

        return score
