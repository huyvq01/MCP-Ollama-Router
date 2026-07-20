class RoutingPolicy:

    def score(
        self,
        model,
        capability,
    ):

        score = 0

        if capability in model.capabilities:
            score += 100

        score -= model.priority

        return score