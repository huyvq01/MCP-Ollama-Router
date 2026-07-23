from pydantic import BaseModel, Field

from app.models.message import Message


class ChatRequest(BaseModel):
    model: str

    messages: list[Message]

    stream: bool = False

    temperature: float = 0.7

    max_tokens: int | None = None

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
