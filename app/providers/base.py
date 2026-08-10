from abc import ABC, abstractmethod

from app.models.chat import ChatRequest, ChatResult
from app.models.provider import ModelInfo


class BaseProvider(ABC):
    @abstractmethod
    async def startup(self) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...

    @abstractmethod
    async def list_model_details(
        self,
    ) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResult:
        ...