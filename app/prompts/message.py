from app.config import (
    MAX_CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_TOKENS,
)
from app.models.message import Message
from app.prompts.system import SYSTEM_PROMPT
from app.services.token_budget import (
    estimate_message_tokens,
    trim_messages_to_tokens,
    truncate_text_to_tokens,
)


class MessageBuilder:
    """
    Build the final message list sent to Ollama.

    The final input context is strictly bounded and
    reserves space for the model output.
    """

    def build(
        self,
        history: list[Message],
        prompt: str,
    ) -> list[Message]:
        # --------------------------------------------------
        # 1. Limit current user prompt
        # --------------------------------------------------

        prompt = truncate_text_to_tokens(
            prompt,
            MAX_PROMPT_TOKENS,
        )

        # --------------------------------------------------
        # 2. Build system and user messages
        # --------------------------------------------------

        system_message: Message = {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }

        user_message: Message = {
            "role": "user",
            "content": prompt,
        }

        # --------------------------------------------------
        # 3. Reserve output tokens
        # --------------------------------------------------

        input_budget = (
            MAX_CONTEXT_TOKENS
            - MAX_OUTPUT_TOKENS
        )

        if input_budget < 0:
            input_budget = 0

        # --------------------------------------------------
        # 4. Calculate system + user tokens
        # --------------------------------------------------

        system_tokens = estimate_message_tokens(
            system_message,
        )

        user_tokens = estimate_message_tokens(
            user_message,
        )

        history_budget = (
            input_budget
            - system_tokens
            - user_tokens
        )

        if history_budget < 0:
            history_budget = 0

        # --------------------------------------------------
        # 5. Trim history
        # --------------------------------------------------

        trimmed_history = trim_messages_to_tokens(
            history,
            history_budget,
        )

        # --------------------------------------------------
        # 6. Build final messages
        # --------------------------------------------------

        messages: list[Message] = [
            system_message,
        ]

        messages.extend(trimmed_history)

        messages.append(user_message)

        return messages