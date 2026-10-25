from time import perf_counter
from typing import Any

import httpx

from app.core.settings import settings
from app.models.chat import ChatRequest, ChatResult
from app.providers.base import BaseProvider
from app.providers.config import ollama_config


class OllamaProvider(BaseProvider):
    def __init__(self) -> None:
        self.client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        if self.client is not None:
            return
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(ollama_config.timeout, connect=5.0, pool=5.0),
            trust_env=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        )

    async def shutdown(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            raise RuntimeError("Provider not started.")

        return self.client

    async def health(self) -> bool:
        response = await self._client().get(
            f"{ollama_config.base_url}/api/tags",
            timeout=5.0,
        )

        return response.status_code == 200

    async def list_models(self) -> list[str]:
        response = await self._client().get(
            f"{ollama_config.base_url}/api/tags",
            timeout=5.0,
        )

        response.raise_for_status()

        data: dict[str, Any] = response.json()

        models = data.get("models", [])

        if not isinstance(models, list):
            return []

        result: list[str] = []

        for model in models:
            if not isinstance(model, dict):
                continue

            name = model.get("name")

            if isinstance(name, str):
                result.append(name)

        return result

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResult:
        if request.stream:
            raise ValueError(
                "Streaming is not supported by this MCP tool; use stream=False."
            )
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_ctx": settings.num_ctx,
            "num_predict": request.max_tokens or settings.max_tokens,
        }

        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        if request.top_p is not None:
            options["top_p"] = request.top_p

        if request.stop is not None:
            options["stop"] = request.stop

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "keep_alive": settings.keep_alive,
            "options": options,
        }

        start = perf_counter()

        response = await self._client().post(
            f"{ollama_config.base_url}/api/chat",
            json=payload,
        )

        elapsed = int((perf_counter() - start) * 1000)

        response.raise_for_status()

        data: dict[str, Any] = response.json()

        prompt_tokens = data.get(
            "prompt_eval_count",
            0,
        )

        completion_tokens = data.get(
            "eval_count",
            0,
        )

        if not isinstance(prompt_tokens, int):
            prompt_tokens = 0

        if not isinstance(completion_tokens, int):
            completion_tokens = 0

        message = data.get("message", {})

        content = ""

        if isinstance(message, dict):
            raw_content = message.get("content", "")

            if isinstance(raw_content, str):
                content = raw_content

        eval_ns = data.get("eval_duration", 0)
        load_ns = data.get("load_duration", 0)
        tokens_per_second = (
            round(completion_tokens / (eval_ns / 1e9), 2)
            if isinstance(eval_ns, (int, float)) and eval_ns > 0
            else 0
        )
        load_ms = int(load_ns / 1e6) if isinstance(load_ns, (int, float)) else 0
        return ChatResult(
            provider="ollama",
            model=request.model,
            content=content,
            finish_reason=data.get("done_reason"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(prompt_tokens + completion_tokens),
            latency_ms=elapsed,
            load_ms=max(0, load_ms),
            tokens_per_second=tokens_per_second,
        )
