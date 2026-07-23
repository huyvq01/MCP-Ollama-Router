from pydantic import BaseModel


class ModelInfo(BaseModel):
    provider: str
    name: str
    capabilities: list[str]
    priority: int = 100
