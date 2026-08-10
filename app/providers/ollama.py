from time import perf_counter
from typing import Any

import httpx

from app.models.chat import ChatRequest, ChatResult
from app.models.provider import ModelInfo
from app.providers.base import BaseProvider
from app.providers.config import ollama_config


class OllamaProvider(BaseProvider):
    def __init__(self) -> None:
        self.client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        if self.client is not None:
            return

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=ollama_config.timeout,
                write=30.0,
                pool=10.0,
            ),
        )

    async def shutdown(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            raise RuntimeError(
                "Provider not started."
            )

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

        models = data.get(
            "models",
            [],
        )

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

    async def list_model_details(
        self,
    ) -> list[ModelInfo]:
        response = await self._client().get(
            f"{ollama_config.base_url}/api/tags",
        )

        response.raise_for_status()

        data: dict[str, Any] = response.json()

        raw_models = data.get(
            "models",
            [],
        )

        if not isinstance(raw_models, list):
            return []

        result: list[ModelInfo] = []

        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue

            name = raw_model.get("name")

            if not isinstance(name, str):
                continue

            details = raw_model.get(
                "details",
                {},
            )

            if not isinstance(details, dict):
                details = {}

            family = details.get(
                "family",
                "",
            )

            parameter_size = details.get(
                "parameter_size",
                "",
            )

            quantization = details.get(
                "quantization_level",
                "",
            )

            context_length = raw_model.get(
                "context_length",
                0,
            )

            capabilities = raw_model.get(
                "capabilities",
                [],
            )

            if not isinstance(family, str):
                family = ""

            if not isinstance(parameter_size, str):
                parameter_size = ""

            if not isinstance(quantization, str):
                quantization = ""

            if not isinstance(context_length, int):
                context_length = 0

            if not isinstance(capabilities, list):
                capabilities = []

            normalized_capabilities = [
                value
                for value in capabilities
                if isinstance(value, str)
            ]

            result.append(
                ModelInfo(
                    provider="ollama",
                    name=name,
                    family=family,
                    parameter_size=parameter_size,
                    quantization=quantization,
                    context_length=context_length,
                    capabilities=normalized_capabilities,
                )
            )

        return result

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResult:
        options: dict[str, Any] = {
            "temperature": request.temperature,

            # Runtime limit for 16 GB machines.
            "num_ctx": ollama_config.num_ctx,

            # Prevent unbounded generation.
            "num_predict": (
                request.max_tokens
                if request.max_tokens is not None
                else ollama_config.num_predict
            ),
        }

        if request.top_p is not None:
            options["top_p"] = request.top_p

        if request.stop is not None:
            options["stop"] = request.stop

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "keep_alive": ollama_config.keep_alive,
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

        message = data.get(
            "message",
            {},
        )

        content = ""

        if isinstance(message, dict):
            raw_content = message.get(
                "content",
                "",
            )

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