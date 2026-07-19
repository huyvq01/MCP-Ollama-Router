from pydantic import BaseModel


class APIResponse(BaseModel):

    success: bool

    message: str | None = None

    data: dict | list | None = None