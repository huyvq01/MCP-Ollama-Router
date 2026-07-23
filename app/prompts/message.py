from app.models.message import Message
from app.prompts.system import SYSTEM_PROMPT


class MessageBuilder:
    def build(
        self,
        history: list[Message],
        prompt: str,
    ) -> list[Message]:
        messages: list[Message] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        return messages
