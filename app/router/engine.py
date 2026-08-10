import logging

from app.models.chat import ChatRequest
from app.prompts.builder import builder
from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.fallback import FallbackManager
from app.router.selector import ModelSelector
from app.services.history import HistoryManager


logger = logging.getLogger(__name__)


class RouterEngine:
    """
    Main routing engine.

    Optimized for:
        - 16 GB RAM
        - CPU-only Ollama
        - small local models
        - bounded context
        - controlled fallback
    """

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
        # ----------------------------------------------------
        # 1. Select initial model
        # ----------------------------------------------------

        if model is None:
            selected: ModelMetadata | None = (
                await self.selector.select(prompt)
            )
        else:
            selected = self._registry.model(model)

            if selected is None:
                raise RuntimeError(
                    f"Model '{model}' not found."
                )

        if selected is None:
            raise RuntimeError(
                "No model available."
            )

        # ----------------------------------------------------
        # 2. Build conversation context
        # ----------------------------------------------------

        history = self._history.get(
            session_id,
        )

        messages = builder.build(
            history,
            prompt,
        )

        logger.info(
            "Chat request: session=%s model=%s messages=%s",
            session_id,
            selected.name,
            len(messages),
        )

        # ----------------------------------------------------
        # 3. Build fallback candidates
        # ----------------------------------------------------

        candidates = self._build_candidates(
            selected,
        )

        # ----------------------------------------------------
        # 4. Try selected model and fallbacks
        # ----------------------------------------------------

        current: ModelMetadata | None = selected

        attempted: set[str] = set()

        while current is not None:
            # Prevent duplicate attempts.
            if current.name in attempted:
                current = self.fallback.next(
                    current,
                    candidates,
                )
                continue

            attempted.add(current.name)

            # ------------------------------------------------
            # 5. Skip models that are too large for 16 GB
            # ------------------------------------------------

            if self._is_unsupported_large_model(
                current,
            ):
                logger.warning(
                    "Skipping large model for 16 GB profile: %s",
                    current.name,
                )

                current = self.fallback.next(
                    current,
                    candidates,
                )

                continue

            # ------------------------------------------------
            # 6. Resolve provider
            # ------------------------------------------------

            provider = self._provider_registry.get(
                current.provider,
            )

            if provider is None:
                logger.warning(
                    "Provider not found: %s",
                    current.provider,
                )

                current = self.fallback.next(
                    current,
                    candidates,
                )

                continue

            # ------------------------------------------------
            # 7. Call provider
            # ------------------------------------------------

            try:
                logger.info(
                    "Calling model=%s provider=%s",
                    current.name,
                    current.provider,
                )

                request = ChatRequest(
                    model=current.name,
                    messages=messages,
                )

                result = await provider.chat(
                    request,
                )

                # ------------------------------------------------
                # 8. Store history only after successful response
                # ------------------------------------------------

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

                logger.info(
                    "Chat completed: model=%s latency_ms=%s "
                    "prompt_tokens=%s completion_tokens=%s",
                    result.model,
                    result.latency_ms,
                    result.prompt_tokens,
                    result.completion_tokens,
                )

                return result.content

            except Exception:
                logger.exception(
                    "Model request failed: "
                    "model=%s provider=%s",
                    current.name,
                    current.provider,
                )

                current = self.fallback.next(
                    current,
                    candidates,
                )

        raise RuntimeError(
            "No available model could complete the request."
        )

    def _build_candidates(
        self,
        selected: ModelMetadata,
    ) -> list[ModelMetadata]:
        """
        Build fallback candidates.

        Smaller models are preferred on a 16 GB machine.
        """

        models = self._registry.enabled()

        # Keep only models suitable for the 16 GB profile.
        models = [
            model
            for model in models
            if not self._is_unsupported_large_model(
                model,
            )
        ]

        # Selected model always gets first attempt.
        remaining = [
            model
            for model in models
            if model.name != selected.name
        ]

        remaining.sort(
            key=self._fallback_score,
            reverse=True,
        )

        return [
            selected,
            *remaining,
        ]

    @staticmethod
    def _fallback_score(
        model: ModelMetadata,
    ) -> int:
        """
        Prefer smaller models for fallback.

        Preference:

            0.5B -> highest
            1B   -> high
            1.5B -> high
            3B   -> high
            7B   -> lower
            8B   -> lower
        """

        name = model.name.lower()

        if "0.5b" in name:
            size_score = 50

        elif "1.5b" in name:
            size_score = 45

        elif "1b" in name:
            size_score = 45

        elif "3b" in name:
            size_score = 35

        elif "7b" in name:
            size_score = 25

        elif "8b" in name:
            size_score = 20

        else:
            size_score = 0

        return size_score + model.priority

    @staticmethod
    def _is_unsupported_large_model(
        model: ModelMetadata,
    ) -> bool:
        """
        Reject models larger than 8B for the
        16 GB RAM CPU-only profile.
        """

        name = model.name.lower()

        large_markers = (
            "12b",
            "14b",
            "20b",
            "27b",
            "32b",
            "34b",
            "70b",
        )

        return any(
            marker in name
            for marker in large_markers
        )

    def clear(
        self,
        session_id: str,
    ) -> None:
        self._history.clear(
            session_id,
        )

    def sessions(
        self,
    ) -> list[str]:
        return self._history.sessions()