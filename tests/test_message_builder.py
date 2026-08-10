from app.config import MAX_CONTEXT_TOKENS, MAX_OUTPUT_TOKENS
from app.models.message import Message
from app.prompts.message import MessageBuilder
from app.services.token_budget import estimate_message_tokens


def total_tokens(messages: list[Message]) -> int:
    return sum(
        estimate_message_tokens(message)
        for message in messages
    )


def test_message_builder_reserves_output_budget() -> None:
    builder = MessageBuilder()

    history: list[Message] = []

    for index in range(20):
        history.append(
            {
                "role": "user",
                "content": "x" * 1000,
            }
        )

    messages = builder.build(
        history=history,
        prompt="Reply with exactly: OK",
    )

    input_tokens = total_tokens(messages)

    input_budget = (
        MAX_CONTEXT_TOKENS
        - MAX_OUTPUT_TOKENS
    )

    assert input_tokens <= input_budget