from pydantic import BaseModel


class ChatRequest(BaseModel):

    session_id: str

    prompt: str

    model: str | None = None


class ChatResponse(BaseModel):

    model: str

    answer: str