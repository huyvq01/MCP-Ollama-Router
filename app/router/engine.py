import asyncio
import logging
import re
from uuid import uuid4

import httpx

from app.config import MAX_REQUEST_OUTPUT_TOKENS
from app.models.chat import ChatRequest
from app.prompts.builder import builder
from app.providers.registry import ProviderRegistry
from app.registry.schemas import ModelMetadata
from app.registry.service import RegistryService
from app.router.fallback import FallbackManager
from app.router.model_size import supported
from app.router.selector import ModelSelector
from app.router.tasks import analyze
from app.runtime import RuntimeSettings, runtime
from app.services.control import CircuitBreaker, RequestGate, RoutingTimeout, SessionLocks
from app.services.history import HistoryManager

logger = logging.getLogger(__name__)


class RouterEngine:
    """Single-process bounded routing with a total deadline and atomic turns."""
    def __init__(self, provider_registry: ProviderRegistry, registry: RegistryService,
                 history: HistoryManager, *, gate: RequestGate | None = None,
                 config: RuntimeSettings = runtime) -> None:
        self._provider_registry = provider_registry
        self._registry = registry
        self._history = history
        self.config = config
        self.gate = gate if gate is not None else RequestGate(config)
        self._sessions = SessionLocks()
        self.breaker = CircuitBreaker(config)
        self.selector = ModelSelector(registry)
        self.fallback = FallbackManager()

    async def chat(self, session_id: str, prompt: str, model: str | None = None,
                   max_tokens: int | None = None) -> str:
        if not re.fullmatch(r'[\w.-]{1,128}', session_id):
            raise ValueError('session_id must contain 1-128 letters, digits, dots, underscores or hyphens.')
        if not prompt.strip() or len(prompt) > self.config.max_prompt_chars:
            raise ValueError('Prompt is empty or exceeds the configured character limit.')
        if max_tokens is not None and not 1 <= max_tokens <= MAX_REQUEST_OUTPUT_TOKENS:
            raise ValueError(f'max_tokens must be between 1 and {MAX_REQUEST_OUTPUT_TOKENS}.')
        request_id = uuid4().hex
        try:
            async with asyncio.timeout(self.config.request_timeout_s):
                async with self.gate.slot():
                    async with self._sessions.hold(session_id):
                        return await self._chat(session_id, prompt, model, max_tokens, request_id)
        except TimeoutError as exc:
            logger.warning('request_timeout request_id=%s', request_id)
            raise RoutingTimeout('Request deadline exceeded; try a shorter prompt or smaller model.') from exc

    async def _chat(self, session_id: str, prompt: str, model: str | None,
                    max_tokens: int | None, request_id: str) -> str:
        revision = self._history.revision(session_id)
        history = self._history.get(session_id)
        profile = analyze(prompt, history)
        output_tokens = max_tokens if max_tokens is not None else min(
            profile.max_tokens, self.config.max_output_tokens,
        )
        if model is None:
            selected = await self.selector.select(profile.routing_prompt)
        else:
            selected = self._registry.model(model)
            if selected is None:
                raise RuntimeError(f"Model '{model}' not found.")
            if not selected.enabled or not supported(selected):
                raise ValueError('Requested model is disabled or exceeds the configured size limit.')
        messages = builder.build(
            history, prompt, instruction=profile.instruction, output_tokens=output_tokens,
        )
        if messages and messages[-1]['content'] != prompt:
            raise ValueError('Input exceeds the context budget; send a smaller excerpt. No code was analyzed.')
        candidates = self._build_candidates(selected, profile.routing_prompt)
        logger.info('request_start request_id=%s task=%s model=%s max_tokens=%d',
                    request_id, profile.task.value, selected.name, output_tokens)
        attempts = 0
        for current in candidates:
            key = current.provider + ':' + current.name
            if not supported(current) or not current.enabled or not self.breaker.available(key):
                continue
            provider = self._provider_registry.get(current.provider)
            if provider is None:
                continue
            if attempts >= self.config.max_attempts:
                break
            attempts += 1
            try:
                request = ChatRequest(
                    model=current.name, messages=messages, max_tokens=output_tokens,
                    temperature=profile.temperature,
                    think=False if 'thinking' in current.capabilities and profile.task.value != 'reasoning' else None,
                )
                async with asyncio.timeout(self.config.attempt_timeout_s):
                    result = await provider.chat(request)
                if not result.content.strip():
                    raise RuntimeError('Model returned an empty answer.')
            except (httpx.HTTPError, TimeoutError, RuntimeError, ValueError) as exc:
                if (isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code < 500
                        and exc.response.status_code not in (408, 429)):
                    raise RuntimeError('Ollama rejected the request; check model compatibility.') from exc
                self.breaker.failure(key)
                # Never log prompts, answers, raw session identifiers or upstream response bodies.
                logger.warning('attempt_failed request_id=%s model=%s error_type=%s attempt=%d',
                               request_id, current.name, type(exc).__name__, attempts)
                continue
            self.breaker.success(key)
            self._history.append_turn(
                session_id, prompt, result.content, expected_revision=revision,
            )
            logger.info('request_complete request_id=%s model=%s latency_ms=%d finish_reason=%s',
                        request_id, current.name, result.latency_ms, result.finish_reason)
            if result.finish_reason == 'length':
                return result.content + '\n\n[Response reached its length limit; ask to continue.]'
            return result.content
        raise RuntimeError('No available model could complete the request.')

    def _build_candidates(self, selected: ModelMetadata, prompt: str = '') -> list[ModelMetadata]:
        result = [selected]
        seen = {selected.name}
        for candidate in self.selector.rank(prompt):
            if candidate.name not in seen:
                result.append(candidate)
                seen.add(candidate.name)
        return result

    @staticmethod
    def _is_unsupported_large_model(model: ModelMetadata) -> bool:
        return not supported(model)

    def clear(self, session_id: str) -> None:
        self._history.clear(session_id)

    def sessions(self) -> list[str]:
        return self._history.sessions()
