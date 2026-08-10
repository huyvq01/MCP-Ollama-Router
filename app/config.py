"""
Global configuration for MCP Ollama Router.
"""

from pathlib import Path


# ============================================================
# Project
# ============================================================

PROJECT_NAME = "MCP Ollama Router"
PROJECT_VERSION = "1.0.0"

ROOT_DIR = Path(__file__).parent
LOG_DIR = ROOT_DIR / "logs"


# ============================================================
# Ollama
# ============================================================

OLLAMA_HOST = "http://127.0.0.1:11434"

OLLAMA_CHAT_API = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_API = f"{OLLAMA_HOST}/api/tags"
OLLAMA_GENERATE_API = f"{OLLAMA_HOST}/api/generate"

# CPU-only laptop:
# Do not allow a single request to block forever.
REQUEST_TIMEOUT = 120


# ============================================================
# Default Model
# ============================================================

# Lightweight default for 16 GB RAM / CPU-only.
DEFAULT_MODEL = "qwen2.5-coder:3b"


# ============================================================
# History / Context
# ============================================================

# Maximum number of stored messages.
MAX_HISTORY = 6

# Maximum history tokens sent to the model.
MAX_HISTORY_TOKENS = 1536

# Maximum total model context.
MAX_CONTEXT_TOKENS = 4096

# Maximum current user prompt.
MAX_PROMPT_TOKENS = 2048

# Maximum generated output.
MAX_OUTPUT_TOKENS = 512


# ============================================================
# Logging
# ============================================================

LOG_LEVEL = "INFO"
LOG_FILE = LOG_DIR / "router.log"