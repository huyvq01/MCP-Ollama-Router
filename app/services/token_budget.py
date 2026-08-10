from app.models.message import Message


# Lightweight token estimation.
# We intentionally avoid adding a tokenizer dependency just
# to protect a CPU-only local model from oversized prompts.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    return max(
        1,
        (len(text) + CHARS_PER_TOKEN - 1)
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

        result.insert(0, message)
        total += message_tokens

    return result


def truncate_text_to_tokens(
    text: str,
    max_tokens: int,
) -> str:
    if max_tokens <= 0:
        return ""

    max_chars = max_tokens * CHARS_PER_TOKEN

    if len(text) <= max_chars:
        return text

    marker = (
        "\n\n"
        "[Context truncated by MCP Ollama Router]"
        "\n\n"
    )

    available = max_chars - len(marker)

    if available <= 0:
        return text[:max_chars]

    head = available // 2
    tail = available - head

    return (
        text[:head]
        + marker
        + text[-tail:]
    )