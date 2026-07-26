from time import perf_counter
from typing import Any

import httpx

from app.models.chat import ChatRequest, ChatResult
from app.providers.base import BaseProvider
from app.providers.config import ollama_config


class OllamaProvider(BaseProvider):
    def __init__(self) -> None:
        self.client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=ollama_config.timeout,
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
        )

        return response.status_code == 200

    async def list_models(self) -> list[str]:
        response = await self._client().get(
            f"{ollama_config.base_url}/api/tags",
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
        options: dict[str, Any] = {
            "temperature": request.temperature,
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
            "stream": request.stream,
            "options": options,
        }

        start = perf_counter()

        response = await self._client().post(
            f"{ollama_config.base_url}/api/chat",
            json=payload,
        )

        elapsed = int(
            (perf_counter() - start) * 1000
        )

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

        return ChatResult(
            provider="ollama",
            model=request.model,
            content=content,
            finish_reason=(
                "stop"
                if data.get("done")
                else None
            ),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(
                prompt_tokens
                + completion_tokens
            ),
            latency_ms=elapsed,
        )