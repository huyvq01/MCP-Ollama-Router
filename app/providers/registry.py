from typing import Dict

from app.providers.base import BaseProvider
from app.providers.discovery import provider_discovery


class ProviderRegistry:

    def __init__(self):

        self._providers: Dict[str, BaseProvider] = (
            provider_discovery.discover()
        )

    async def startup(self):

        for provider in self._providers.values():
            await provider.startup()

    async def shutdown(self):

        for provider in self._providers.values():
            await provider.shutdown()

    def get(
        self,
        name: str,
    ) -> BaseProvider | None:

        return self._providers.get(name)

    def providers(self):

        return self._providers

    def names(self):

        return list(self._providers.keys())

    async def healthy(self):

        healthy = []

        for name, provider in self._providers.items():

            try:

                if await provider.health():

                    healthy.append(name)

            except Exception:

                pass

        return healthy