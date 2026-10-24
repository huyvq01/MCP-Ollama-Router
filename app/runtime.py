"""Validated process configuration. Secrets are never included in logs."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def env_file_path(source_root: Path | None = None) -> Path:
    explicit = os.environ.get("ROUTER_ENV_FILE")
    if explicit:
        return Path(explicit).expanduser()
    root = source_root if source_root is not None else Path(__file__).resolve().parents[1]
    # Editable installs locate project config even when an MCP host starts in
    # another workspace. Wheel installs use the operator's current directory.
    if (root / "pyproject.toml").is_file():
        return root / ".env"
    return Path.cwd() / ".env"


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROUTER_",
        env_file=env_file_path(),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    request_timeout_s: float = Field(default=90, gt=0, le=1800)
    attempt_timeout_s: float = Field(default=45, gt=0, le=1800)
    queue_timeout_s: float = Field(default=5, gt=0, le=120)
    startup_timeout_s: float = Field(default=10, gt=0, le=120)
    max_concurrent: int = Field(default=1, ge=1, le=16)
    max_pending: int = Field(default=8, ge=1, le=256)
    max_attempts: int = Field(default=2, ge=1, le=5)
    breaker_failures: int = Field(default=2, ge=1, le=20)
    breaker_cooldown_s: float = Field(default=30, gt=0, le=600)
    context_tokens: int = Field(default=4096, ge=2048, le=131072)
    prompt_tokens: int = Field(default=2048, ge=256, le=65536)
    history_tokens: int = Field(default=1536, ge=256, le=65536)
    max_output_tokens: int = Field(default=2048, ge=256, le=16384)
    history_messages: int = Field(default=6, ge=2, le=100)
    max_sessions: int = Field(default=256, ge=1, le=10000)
    session_ttl_s: float = Field(default=3600, gt=0, le=86400)
    max_prompt_chars: int = Field(default=64000, ge=1024, le=1000000)
    max_model_billions: float = Field(default=8, gt=0, le=1000)
    allow_unknown_model_size: bool = False
    keep_alive: str = "15m"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = Field(default=8080, ge=1024, le=65535)
    gateway_context_tokens: int = Field(default=8192, ge=2048, le=131072)
    gateway_api_key: SecretStr | None = None
    max_body_bytes: int = Field(default=262144, ge=4096, le=16777216)
    log_level: str = "INFO"

    @field_validator("ollama_base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Ollama URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Ollama URL must not contain credentials, queries or fragments")
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("Unsupported log level")
        return value

    @model_validator(mode="after")
    def validate_limits(self) -> "RuntimeSettings":
        if self.max_output_tokens + 256 >= self.context_tokens:
            raise ValueError("Context must reserve at least 256 tokens for input")
        if self.max_pending < self.max_concurrent:
            raise ValueError("max_pending must be >= max_concurrent")
        return self


runtime = RuntimeSettings()
