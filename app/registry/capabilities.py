from app.registry.models import MODELS


class CapabilityRegistry:

    def select(
        self,
        prompt: str,
    ):

        prompt = prompt.lower()

        if any(
            word in prompt
            for word in (
                "python",
                "java",
                "code",
                "sql",
                "bug",
                "api",
            )
        ):
            return MODELS[0]

        if any(
            word in prompt
            for word in (
                "reason",
                "logic",
                "math",
                "prove",
            )
        ):
            return MODELS[1]

        return MODELS[2]


registry = CapabilityRegistry()