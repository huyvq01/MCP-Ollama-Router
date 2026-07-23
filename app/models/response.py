from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool
    message: str | None = None
    data: dict[str, Any] | list[Any] | None = None
