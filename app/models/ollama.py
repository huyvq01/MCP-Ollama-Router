from pydantic import BaseModel, Field


class OllamaModelInfo(BaseModel):
    name: str

    family: str = ""

    parameter_size: str = ""

    quantization: str = ""

    context_length: int = 0

    capabilities: list[str] = Field(default_factory=list)