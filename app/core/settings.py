from app.config import (
    DEFAULT_MODEL,
    MAX_CONTEXT_TOKENS,
    MAX_HISTORY,
    MAX_HISTORY_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_TOKENS,
    OLLAMA_CHAT_API,
    OLLAMA_HOST,
    OLLAMA_TAGS_API,
    PROJECT_NAME,
    PROJECT_VERSION,
    REQUEST_TIMEOUT,
)


class Settings:
    project_name = PROJECT_NAME
    version = PROJECT_VERSION

    ollama_host = OLLAMA_HOST
    chat_api = OLLAMA_CHAT_API
    tags_api = OLLAMA_TAGS_API

    timeout = REQUEST_TIMEOUT

    default_model = DEFAULT_MODEL

    max_history = MAX_HISTORY
    max_history_tokens = MAX_HISTORY_TOKENS
    max_context_tokens = MAX_CONTEXT_TOKENS
    max_prompt_tokens = MAX_PROMPT_TOKENS
    max_output_tokens = MAX_OUTPUT_TOKENS

    classifier_provider = "ollama"
    classifier_model = "qwen2.5-coder:7b"


settings = Settings()