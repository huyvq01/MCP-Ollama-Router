import asyncio
import logging

from app.providers.base import BaseProvider
from app.providers.discovery import provider_discovery


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = provider_discovery.discover()

    async def startup(self) -> None:
        for provider in self._providers.values():
            await provider.startup()

    async def shutdown(self) -> None:
        results = await asyncio.gather(
            *(provider.shutdown() for provider in self._providers.values()),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logging.getLogger(__name__).error(
                    "provider_shutdown_failed error_type=%s", type(result).__name__,
                )

    def get(
        self,
        name: str,
    ) -> BaseProvider | None:
        return self._providers.get(name)

    def providers(self) -> dict[str, BaseProvider]:
        return self._providers

    def names(self) -> list[str]:
        return list(self._providers.keys())

    async def healthy(self) -> list[str]:
        healthy: list[str] = []

        for name, provider in self._providers.items():
            try:
                if await provider.health():
                    healthy.append(name)
            except Exception:
                pass

        return healthy
