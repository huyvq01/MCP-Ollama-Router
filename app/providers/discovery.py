from app.providers.base import BaseProvider
from app.providers.ollama import OllamaProvider


class ProviderDiscovery:
    def discover(self) -> dict[str, BaseProvider]:
        return {
            "ollama": OllamaProvider(),
        }


provider_discovery = ProviderDiscovery()
