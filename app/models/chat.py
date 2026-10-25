from pydantic import BaseModel, Field

from app.models.message import Message


class ChatRequest(BaseModel):
    model: str

    messages: list[Message]

    stream: bool = False

    temperature: float = Field(default=0.2, ge=0, le=2)

    max_tokens: int | None = Field(default=512, ge=1, le=4096)

    top_p: float | None = None

    stop: list[str] | None = None


class ChatResult(BaseModel):
    provider: str

    model: str

    content: str

    finish_reason: str | None = None

    prompt_tokens: int = 0

    completion_tokens: int = 0

    total_tokens: int = 0

    latency_ms: int = Field(default=0)

    load_ms: int = Field(default=0, ge=0)

    tokens_per_second: float = Field(default=0, ge=0)
