from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.chat import ChatRequest
from app.providers.config import ollama_config
from app.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_chat_uses_memory_limits() -> None:
    provider = OllamaProvider()

    client = MagicMock()
    client.post = AsyncMock()

    response = MagicMock()

    response.raise_for_status.return_value = None

    response.json.return_value = {
        "message": {
            "content": "OK",
        },
        "done": True,
        "prompt_eval_count": 10,
        "eval_count": 1,
    }

    client.post.return_value = response

    provider.client = client

    request = ChatRequest(
        model="qwen2.5-coder:3b",
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: OK",
            }
        ],
    )

    result = await provider.chat(request)

    assert result.content == "OK"

    client.post.assert_awaited_once()

    kwargs = client.post.call_args.kwargs
    payload = kwargs["json"]

    assert payload["stream"] is False
    assert payload["keep_alive"] == ollama_config.keep_alive

    assert payload["options"]["num_ctx"] == ollama_config.num_ctx
    assert payload["options"]["num_predict"] == ollama_config.num_predict