"""
Global configuration for MCP Ollama Router.
"""

from pathlib import Path

from app.runtime import runtime


# ============================================================
# Project
# ============================================================

PROJECT_NAME = "MCP Ollama Router"
PROJECT_VERSION = "0.2.0"

ROOT_DIR = Path(__file__).parent
LOG_DIR = ROOT_DIR / "logs"


# ============================================================
# Ollama
# ============================================================

OLLAMA_HOST = runtime.ollama_base_url

OLLAMA_CHAT_API = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_API = f"{OLLAMA_HOST}/api/tags"
OLLAMA_GENERATE_API = f"{OLLAMA_HOST}/api/generate"

# CPU-only laptop:
# Do not allow a single request to block forever.
REQUEST_TIMEOUT = runtime.request_timeout_s


# ============================================================
# Default Model
# ============================================================

# Lightweight default for 16 GB RAM / CPU-only.
DEFAULT_MODEL = "qwen2.5-coder:3b"


# ============================================================
# History / Context
# ============================================================

# Maximum number of stored messages.
MAX_HISTORY = runtime.history_messages

# Maximum history tokens sent to the model.
MAX_HISTORY_TOKENS = runtime.history_tokens

# Maximum total model context.
MAX_CONTEXT_TOKENS = runtime.context_tokens

# Maximum current user prompt.
MAX_PROMPT_TOKENS = runtime.prompt_tokens

# Maximum generated output.
MAX_OUTPUT_TOKENS = 512

# Allow complete code/documentation while keeping the total context at 4096.
MAX_REQUEST_OUTPUT_TOKENS = runtime.max_output_tokens
MAX_ROUTER_MODEL_B = runtime.max_model_billions


# ============================================================
# Logging
# ============================================================

LOG_LEVEL = "INFO"
LOG_FILE = LOG_DIR / "router.log"
