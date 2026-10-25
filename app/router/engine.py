import asyncio
import logging
import re
import time
from collections import OrderedDict

import httpx

from app.core.settings import settings
from app.models.chat import ChatRequest
from app.prompts.builder import builder
from app.providers.registry import ProviderRegistry
from app.registry.service import RegistryService
from app.router.fallback import FallbackManager
from app.router.matcher import matcher
from app.router.selector import ModelSelector
from app.services.history import HistoryManager

logger = logging.getLogger(__name__)


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
        self._gate = asyncio.Lock()
        self._metrics: OrderedDict[str, dict[str, object]] = OrderedDict()

    async def chat(
        self,
        session_id: str,
        prompt: str,
        model: str | None = None,
        *,
        mode: str = "auto",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        if not session_id.strip() or len(session_id) > 128 or not prompt.strip():
            raise ValueError(
                "Provide a non-empty prompt and a session_id of 1-128 characters."
            )
        if mode not in {"auto", "code", "report"}:
            raise ValueError("mode must be auto, code or report")
        tokens = max_tokens if max_tokens is not None else settings.max_tokens
        if not 1 <= tokens <= min(4096, settings.num_ctx // 2):
            raise ValueError("max_tokens must be 1..min(4096, num_ctx/2)")
        report = mode == "report" or (
            mode == "auto" and matcher.match(prompt).value == "report"
        )
        temp = temperature if temperature is not None else (0.3 if report else 0.2)
        if not 0 <= temp <= 2:
            raise ValueError("temperature must be between 0 and 2")
        # One active request avoids a long queue on a 4 GB GPU.
        if self._gate.locked():
            raise RuntimeError(
                "Router is busy. Wait for the active request before retrying."
            )
        async with self._gate:
            try:
                async with asyncio.timeout(settings.timeout):
                    return await self._chat(
                        session_id, prompt, model, mode, tokens, temp
                    )
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Ollama exceeded {settings.timeout}s. "
                    "Use the 3b model and a shorter prompt/output."
                ) from exc

    async def _chat(
        self,
        session_id: str,
        prompt: str,
        model: str | None,
        mode: str,
        tokens: int,
        temperature: float,
    ) -> str:
        if mode == "auto":
            mode = "report" if matcher.match(prompt).value == "report" else "code"
        if model is None and mode == "report":
            selected = self._registry.model(settings.report_model)
            if selected is None or not selected.enabled:
                selected = await self.selector.select(prompt)
        else:
            selected = (
                self._registry.model(model)
                if model
                else await self.selector.select(prompt)
            )
        if selected is None:
            raise RuntimeError(f"Model '{model}' not found.")
        if not selected.enabled:
            raise RuntimeError(f"Model '{selected.name}' is disabled.")
        history = self._history.get(session_id)
        messages = builder.build(history, prompt, mode=mode, max_tokens=tokens)

        def parameter_size(name: str) -> float:
            match = re.search(r":(\d+(?:\.\d+)?)b", name.lower())
            return float(match.group(1)) if match else 0

        selected_size = parameter_size(selected.name)
        candidates = [selected]
        if model is None:
            candidates += sorted(
                [
                    m
                    for m in self._registry.enabled()
                    if m.name != selected.name
                    and (
                        not selected_size or 0 < parameter_size(m.name) <= selected_size
                    )
                    and ("general" in m.capabilities or "code" in m.capabilities)
                ],
                key=lambda m: m.priority,
                reverse=True,
            )
        errors = []
        for current in candidates[: settings.max_attempts]:
            provider = self._provider_registry.get(current.provider)
            if provider is None:
                errors.append(f"{current.name}: provider unavailable")
                continue
            start = time.perf_counter()
            try:
                result = await provider.chat(
                    ChatRequest(
                        model=current.name,
                        messages=messages,
                        max_tokens=tokens,
                        temperature=temperature,
                    )
                )
                if not result.content.strip():
                    raise RuntimeError("Model returned empty content")
                self._history.append(session_id, "user", prompt)
                self._history.append(session_id, "assistant", result.content)
                self._metrics[session_id] = {
                    "model": current.name,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000),
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "finish_reason": result.finish_reason,
                    "context": settings.num_ctx,
                    "load_ms": result.load_ms,
                    "tokens_per_second": result.tokens_per_second,
                }
                self._metrics.move_to_end(session_id)
                while len(self._metrics) > settings.max_sessions:
                    self._metrics.popitem(last=False)
                return result.content
            except Exception as exc:
                logger.warning(
                    "Model %s failed: %s: %s", current.name, type(exc).__name__, exc
                )
                errors.append(f"{current.name}: {type(exc).__name__}: {exc}")
                # A timeout or transport failure affects the shared Ollama server too.

                if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
                    break
        raise RuntimeError(
            "No available model could complete the request. " + "; ".join(errors)
        )

    def metrics(self, session_id: str) -> dict[str, object]:
        return dict(self._metrics.get(session_id, {}))

    def clear(self, session_id: str) -> None:
        self._history.clear(session_id)
        self._metrics.pop(session_id, None)

    def sessions(self) -> list[str]:
        return self._history.sessions()
