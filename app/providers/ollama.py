import httpx

from app.providers.base import BaseProvider
from app.providers.config import ollama_config


class OllamaProvider(BaseProvider):

    def __init__(self):

        self.client: httpx.AsyncClient | None = None

    async def startup(self):

        self.client = httpx.AsyncClient(
            timeout=ollama_config.timeout
        )

    async def shutdown(self):

        if self.client:

            await self.client.aclose()

    def _client(self) -> httpx.AsyncClient:

        if self.client is None:

            raise RuntimeError(
                "Provider not started."
            )

        return self.client

    async def health(self):

        r = await self._client().get(
            f"{ollama_config.base_url}/api/tags"
        )

        return r.status_code == 200

    async def list_models(self):

        r = await self._client().get(
            f"{ollama_config.base_url}/api/tags"
        )

        r.raise_for_status()

        data = r.json()

        return [
            m["name"]
            for m in data.get("models", [])
        ]

    async def chat(
        self,
        model,
        messages,
        **kwargs,
    ):

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        payload.update(kwargs)

        r = await self._client().post(
            f"{ollama_config.base_url}/api/chat",
            json=payload,
        )

        r.raise_for_status()

        return r.json()["message"]["content"]