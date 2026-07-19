from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    provider: str
    name: str
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None

    capabilities: list[str] = Field(default_factory=list)

    priority: int = 100

    enabled: bool = True