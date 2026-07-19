from pydantic import BaseModel


class RouteResult(BaseModel):

    provider: str

    model: str