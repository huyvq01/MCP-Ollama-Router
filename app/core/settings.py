from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROUTER_",
        extra="ignore",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
    )
    project_name: str = "MCP Ollama Router"
    version: str = "1.2.0"
    ollama_host: str = "http://127.0.0.1:11434"
    bridge_port: int = Field(default=18080, ge=1, le=65535)
    bridge_auto_tools: bool = True
    timeout: int = Field(default=120, ge=10, le=600)
    default_model: str = "qwen2.5-coder:3b"
    report_model: str = "qwen2.5-coder:3b"
    num_ctx: int = Field(default=4096, ge=1024, le=32768)
    max_tokens: int = Field(default=512, ge=64, le=4096)
    keep_alive: str = "10m"
    max_history: int = Field(default=8, ge=2, le=40)
    max_sessions: int = Field(default=64, ge=1, le=1024)
    session_ttl: int = Field(default=3600, ge=60)
    max_attempts: int = Field(default=2, ge=1, le=3)

    workspace_root: Path = Path(__file__).resolve().parents[2]
    state_dir: Path | None = None
    mendix_project: Path | None = None
    mendix_mx_executable: Path | None = None
    mendix_export_timeout: int = Field(default=600, ge=10, le=1800)
    check_timeout: int = Field(default=120, ge=1, le=600)
    check_commands: dict[str, list[str]] = {
        "tests": ["{python}", "-m", "pytest", "-o", "addopts=", "-q"],
        "lint": ["{python}", "-m", "ruff", "check", "app"],
    }
    enable_git_network: bool = False
    enable_publish: bool = False
    github_token: SecretStr | None = None
    document_hosts: list[str] = [
        "docs.mendix.com",
        "docs.oracle.com",
        "docs.python.org",
        "modelcontextprotocol.io",
        "gofastmcp.com",
        "docs.ollama.com",
        "raw.githubusercontent.com",
        "github.com",
    ]
    transport: str = "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = Field(default=8000, ge=1, le=65535)
    http_public_url: str = "http://127.0.0.1:8000"
    jwt_secret: SecretStr | None = None
    jwt_jwks_uri: str | None = None
    jwt_issuer: str = "mcp-ollama-router"
    jwt_audience: str = "mcp-ollama-router"
    authorization_servers: list[str] = []
    http_allowed_hosts: list[str] = ["127.0.0.1", "localhost", "testserver"]
    http_allowed_origins: list[str] = []

    @property
    def chat_api(self) -> str:
        return f"{self.ollama_host}/api/chat"

    @property
    def tags_api(self) -> str:
        return f"{self.ollama_host}/api/tags"


settings = Settings()
