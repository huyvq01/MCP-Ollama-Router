from app.prompts.system import SYSTEM_PROMPT


class MessageBuilder:

    def build(
        self,
        history,
        prompt,
    ):

        messages = [
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