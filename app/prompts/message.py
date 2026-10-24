from app.config import (
    MAX_CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_TOKENS,
    MAX_REQUEST_OUTPUT_TOKENS,
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
        *,
        instruction: str = "",
        output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> list[Message]:
        if not 1 <= output_tokens <= MAX_REQUEST_OUTPUT_TOKENS:
            raise ValueError("Invalid output token budget.")
        system_content = SYSTEM_PROMPT
        if instruction:
            system_content += "\n\n" + instruction
        system_message: Message = {"role": "system", "content": system_content}
        # Reserve the current task's actual output budget before truncating
        # input. This also handles longer code/documentation responses.
        input_budget = MAX_CONTEXT_TOKENS - output_tokens
        prompt_budget = min(
            MAX_PROMPT_TOKENS,
            max(0, input_budget - estimate_message_tokens(system_message) - 4),
        )
        # --------------------------------------------------
        # 1. Limit current user prompt
        # --------------------------------------------------

        prompt = truncate_text_to_tokens(
            prompt,
            prompt_budget,
        )

        # --------------------------------------------------
        # 2. Build system and user messages
        # --------------------------------------------------

        user_message: Message = {
            "role": "user",
            "content": prompt,
        }

        # --------------------------------------------------
        # 3. Reserve output tokens
        # --------------------------------------------------

        input_budget = (
            MAX_CONTEXT_TOKENS
            - output_tokens
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
