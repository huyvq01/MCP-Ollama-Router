from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"

    timeout: float = 120.0

    # 16 GB RAM / CPU-only profile.
    num_ctx: int = 4096

    # Keep model loaded for consecutive requests.
    keep_alive: str = "5m"

    # Maximum generated tokens.
    num_predict: int = 512


ollama_config = OllamaConfig()