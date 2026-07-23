from time import perf_counter

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

        data = response.json()

        return [model["name"] for model in data.get("models", [])]

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResult:
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": request.stream,
            "options": {
                "temperature": request.temperature,
            },
        }

        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        if request.top_p is not None:
            payload["options"]["top_p"] = request.top_p

        if request.stop is not None:
            payload["options"]["stop"] = request.stop

        start = perf_counter()

        response = await self._client().post(
            f"{ollama_config.base_url}/api/chat",
            json=payload,
        )

        elapsed = int((perf_counter() - start) * 1000)

        response.raise_for_status()

        data = response.json()

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return ChatResult(
            provider="ollama",
            model=request.model,
            content=data["message"]["content"],
            finish_reason="stop" if data.get("done") else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=elapsed,
        )
