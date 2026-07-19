from app.config import *

class Settings:

    project_name = PROJECT_NAME

    version = PROJECT_VERSION

    ollama_host = OLLAMA_HOST

    chat_api = OLLAMA_CHAT_API

    tags_api = OLLAMA_TAGS_API

    timeout = REQUEST_TIMEOUT

    default_model = DEFAULT_MODEL

    max_history = MAX_HISTORY
    classifier_provider = "ollama"
    classifier_model = "qwen2.5-coder:7b"


settings = Settings()