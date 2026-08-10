from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    provider: str

    name: str

    family: str = ""

    parameter_size: str = ""

    quantization: str = ""

    context_length: int = 0

    capabilities: list[str] = Field(
        default_factory=list,
    )

    priority: int = 100

    enabled: bool = True