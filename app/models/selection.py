from pydantic import BaseModel


class ModelSelection(BaseModel):
    provider: str
    model: str
    reason: str | None = None