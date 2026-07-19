from app.registry import registry_service
from app.router.matcher import matcher


class ModelSelector:

    async def select(
        self,
        prompt: str,
    ):

        capability = matcher.match(prompt)

        candidates = [
            model
            for model in registry_service.models()
            if model.enabled
        ]

        for model in candidates:

            if capability in model.capabilities:

                return (
                    model.provider,
                    model.name,
                )

        if not candidates:
            raise RuntimeError("No available model.")

        default = min(
            candidates,
            key=lambda x: x.priority,
        )

        return (
            default.provider,
            default.name,
        )