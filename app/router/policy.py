from app.registry.schemas import ModelMetadata


class RoutingPolicy:
    def score(
        self,
        model: ModelMetadata,
        capability: str,
    ) -> int:
        score = 0

        if capability in model.capabilities:
            score += 100

        score -= model.priority

        return score
