from typing import Dict

from app.providers.base import BaseProvider
from app.providers.ollama import OllamaProvider


class ProviderRegistry:

    def __init__(self):

        self._providers: Dict[str, BaseProvider] = {
            "ollama": OllamaProvider()
        }

    async def startup(self):

        for provider in self._providers.values():
            await provider.startup()

    async def shutdown(self):

        for provider in self._providers.values():
            await provider.shutdown()

    def get(self, name: str) -> BaseProvider | None:

        return self._providers.get(name)

    def providers(self):

        return self._providers