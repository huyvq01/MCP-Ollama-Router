from dataclasses import dataclass

from app.runtime import runtime


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = runtime.ollama_base_url

    timeout: float = runtime.attempt_timeout_s

    # 16 GB RAM / CPU-only profile.
    num_ctx: int = runtime.context_tokens

    # Keep model loaded for consecutive requests.
    keep_alive: str = runtime.keep_alive

    # Maximum generated tokens.
    num_predict: int = 512


ollama_config = OllamaConfig()
