from app.providers.ollama import OllamaProvider


class ProviderDiscovery:

    def discover(self):

        return {
            "ollama": OllamaProvider(),
        }


provider_discovery = ProviderDiscovery()