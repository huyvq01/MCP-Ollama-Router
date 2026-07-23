from app.models.chat import ChatRequest
from app.prompts.builder import builder
from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.fallback import FallbackManager
from app.router.selector import ModelSelector
from app.services.history import HistoryManager


class RouterEngine:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
        registry: RegistryService,
        history: HistoryManager,
    ) -> None:
        self._provider_registry = provider_registry
        self._registry = registry
        self._history = history

        self.selector = ModelSelector(registry)
        self.fallback = FallbackManager()

    async def chat(
        self,
        session_id: str,
        prompt: str,
        model: str | None = None,
    ) -> str:
        history = self._history.get(session_id)

        messages = builder.build(
            history,
            prompt,
        )

        if model is None:
            selected = await self.selector.select(prompt)
        else:
            selected = self._registry.model(model)

            if selected is None:
                raise RuntimeError(f"Model '{model}' not found.")

        candidates = sorted(
            self._registry.enabled(),
            key=lambda m: m.priority,
            reverse=True,
        )

        current: ModelMetadata | None = selected

        while current is not None:
            provider = self._provider_registry.get(
                current.provider,
            )

            if provider is None:
                current = self.fallback.next(
                    current,
                    candidates,
                )
                continue

            try:
                request = ChatRequest(
                    model=current.name,
                    messages=messages,
                )

                result = await provider.chat(request)

                self._history.append(
                    session_id,
                    "user",
                    prompt,
                )

                self._history.append(
                    session_id,
                    "assistant",
                    result.content,
                )

                return result.content

            except Exception:
                current = self.fallback.next(
                    current,
                    candidates,
                )

        raise RuntimeError("No available model could complete the request.")

    def clear(
        self,
        session_id: str,
    ) -> None:
        self._history.clear(session_id)

    def sessions(self) -> list[str]:
        return self._history.sessions()
