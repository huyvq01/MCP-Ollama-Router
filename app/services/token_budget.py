from app.models.message import Message


# Lightweight token estimation.
# We intentionally avoid adding a tokenizer dependency just
# to protect a CPU-only local model from oversized prompts.
CHARS_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    return max(
        1,
        (len(text.encode("utf-8")) + CHARS_PER_TOKEN - 1)
        // CHARS_PER_TOKEN,
    )


def estimate_message_tokens(
    message: Message,
) -> int:
    # Small overhead for role/message formatting.
    return estimate_tokens(
        message["content"],
    ) + 4


def trim_messages_to_tokens(
    messages: list[Message],
    max_tokens: int,
) -> list[Message]:
    if max_tokens <= 0:
        return []

    result: list[Message] = []
    total = 0

    for message in reversed(messages):
        message_tokens = estimate_message_tokens(
            message,
        )

        if total + message_tokens > max_tokens:
            break

        result.append(message)
        total += message_tokens

    result.reverse()
    return result


def truncate_text_to_tokens(
    text: str,
    max_tokens: int,
) -> str:
    if max_tokens <= 0:
        return ""

    # Bound UTF-8 bytes, not code points: Vietnamese/CJK source and emoji
    # otherwise exceed the estimate used to build the context.
    encoded = text.encode("utf-8")
    max_bytes = max_tokens * CHARS_PER_TOKEN
    if len(encoded) <= max_bytes:
        return text
    marker = b"\n\n[Context truncated by MCP Ollama Router]\n\n"
    available = max_bytes - len(marker)
    if available <= 0:
        return encoded[:max_bytes].decode("utf-8", errors="ignore")
    head = available // 2
    tail = available - head
    return (
        encoded[:head].decode("utf-8", errors="ignore")
        + marker.decode("ascii")
        + encoded[-tail:].decode("utf-8", errors="ignore")
    )
