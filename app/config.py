"""Compatibility exports; runtime settings live in app.core.settings."""

from pathlib import Path

from app.core.settings import settings

PROJECT_NAME = settings.project_name
PROJECT_VERSION = settings.version
ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "logs"
OLLAMA_HOST = settings.ollama_host
OLLAMA_CHAT_API = settings.chat_api
OLLAMA_TAGS_API = settings.tags_api
OLLAMA_GENERATE_API = f"{OLLAMA_HOST}/api/generate"
REQUEST_TIMEOUT = settings.timeout
DEFAULT_MODEL = settings.default_model
MAX_HISTORY = settings.max_history
LOG_LEVEL = "INFO"
LOG_FILE = LOG_DIR / "router.log"
