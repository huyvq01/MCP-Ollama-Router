from app.dependencies import container


def test_history_append_get_clear():
    history = container.history

    history.clear("demo")

    history.append(
        "demo",
        "user",
        "Hello",
    )

    history.append(
        "demo",
        "assistant",
        "Hi!",
    )

    messages = history.get("demo")

    assert len(messages) == 2

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi!"

    history.clear("demo")

    assert history.get("demo") == []
