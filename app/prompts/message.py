from app.core.settings import settings
from app.models.message import Message
from app.prompts.system import SYSTEM_PROMPT


class MessageBuilder:
    def build(
        self,
        history: list[Message],
        prompt: str,
        *,
        mode: str = "auto",
        max_tokens: int | None = None,
    ) -> list[Message]:
        system = SYSTEM_PROMPT
        if mode == "report":
            system += (
                " Write a structured Vietnamese technical report unless another "
                "language is requested. Separate facts, assumptions and missing "
                "evidence. Never invent citations, measurements or project "
                "results."
            )
        elif mode == "code":
            system += (
                " Prioritize correct, minimal Java/Mendix code. Respect supplied "
                "JDK and Studio Pro versions. Include tests or explanations "
                "only when requested. For method-only requests, return the "
                "method alone without boilerplate."
            )
        output = max_tokens or settings.max_tokens
        # UTF-8 bytes are a conservative token upper bound, not an exact tokenizer.
        budget = settings.num_ctx - output - 256

        def cost(m: Message) -> int:
            return len(m["content"].encode("utf-8")) + 16

        first: Message = {"role": "system", "content": system}
        last: Message = {"role": "user", "content": prompt}
        remaining = budget - cost(first) - cost(last)
        if remaining < 0:
            raise ValueError(
                "Prompt exceeds the safe context budget. Split the code/document "
                "into smaller sections or reduce max_tokens."
            )
        selected: list[Message] = []
        # Keep complete user/assistant turns; drop oldest turns before generation.
        end = len(history)
        while end >= 2:
            pair = history[end - 2 : end]
            if pair[0]["role"] != "user" or pair[1]["role"] != "assistant":
                end -= 1
                continue
            size = sum(cost(m) for m in pair)
            if size > remaining:
                break
            selected = pair + selected
            remaining -= size
            end -= 2
        return [first, *selected, last]
