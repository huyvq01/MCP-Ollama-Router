from abc import ABC, abstractmethod


class BaseProvider(ABC):

    name: str

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
    async def chat(
        self,
        model: str,
        messages: list[dict],
        **kwargs,
    ) -> str:
        ...