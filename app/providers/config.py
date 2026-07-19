from pydantic import BaseModel

from app.core.settings import settings


class OllamaConfig(BaseModel):

    base_url: str = settings.ollama_host

    timeout: int = settings.timeout


ollama_config = OllamaConfig()