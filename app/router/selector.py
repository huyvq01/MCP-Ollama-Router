from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.model_size import parameter_billions, supported
from app.router.policy import RoutingPolicy
from app.router.tasks import Task, TaskProfile, analyze


class ModelSelector:
    def __init__(
        self,
        registry: RegistryService,
    ) -> None:
        self._registry = registry
        self.policy = RoutingPolicy()

    async def select(
        self,
        prompt: str,
    ) -> ModelMetadata:
        models = self.rank(prompt)
        if not models:
            raise RuntimeError(
                "No available model within the configured size limit."
            )
        return models[0]

    def rank(self, prompt: str, *, require_tools: bool = False) -> list[ModelMetadata]:
        profile = analyze(prompt)
        return sorted(
            (model for model in self._registry.enabled()
             if supported(model) and (not require_tools or "tools" in model.capabilities)),
            key=lambda model: (
                self._score(model, profile),
                -(parameter_billions(model) or 999.0),
                model.name,
            ),
            reverse=True,
        )

    def _score(self, model: ModelMetadata, profile: TaskProfile) -> float:
        score = float(self.policy.score(
            model, profile.capability, profile.complexity,
        ))
        size = parameter_billions(model)
        if profile.task in (Task.EXPLAIN, Task.DOCUMENTATION, Task.GENERAL):
            # Prefer a general assistant for prose, while preserving code
            # specialists for actual implementation requests.
            if "code" not in model.capabilities:
                score += 25
            score -= (size * 4) if size is not None else 20
        elif profile.task == Task.CODE:
            score -= (size * 2) if size is not None else 20
        return score
