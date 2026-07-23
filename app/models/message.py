from typing_extensions import TypedDict


class Message(TypedDict):
    role: str
    content: str
