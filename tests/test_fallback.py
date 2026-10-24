from app.registry.schemas import ModelMetadata
from app.router.fallback import FallbackManager


def model(
    name: str,
    priority: int,
) -> ModelMetadata:
    return ModelMetadata(
        provider="ollama",
        name=name,
        capabilities=["general"],
        priority=priority,
    )


def test_next_model() -> None:
    manager = FallbackManager()

    qwen = model("qwen", 100)
    deepseek = model("deepseek", 95)
    gemma = model("gemma", 80)

    candidates = [
        qwen,
        deepseek,
        gemma,
    ]

    assert (
        manager.next(
            qwen,
            candidates,
        )
        == deepseek
    )

    assert (
        manager.next(
            deepseek,
            candidates,
        )
        == gemma
    )

    assert (
        manager.next(
            gemma,
            candidates,
        )
        is None
    )


def test_preserves_candidate_order() -> None:
    manager = FallbackManager()

    qwen = model("qwen", 100)
    deepseek = model("deepseek", 95)
    gemma = model("gemma", 80)

    candidates = [
        gemma,
        qwen,
        deepseek,
    ]

    assert (
        manager.next(
            qwen,
            candidates,
        )
        == deepseek
    )

    # A low-priority selected model must still fall back to earlier
    # priority ranks, following the order supplied by the engine.
    assert manager.next(gemma, candidates) == qwen


def test_current_not_found() -> None:
    manager = FallbackManager()

    qwen = model("qwen", 100)
    deepseek = model("deepseek", 95)

    llama = model("llama", 90)

    assert (
        manager.next(
            llama,
            [
                qwen,
                deepseek,
            ],
        )
        is None
    )


def test_single_model() -> None:
    manager = FallbackManager()

    qwen = model("qwen", 100)

    assert (
        manager.next(
            qwen,
            [
                qwen,
            ],
        )
        is None
    )


def test_empty_candidates() -> None:
    manager = FallbackManager()

    qwen = model("qwen", 100)

    assert (
        manager.next(
            qwen,
            [],
        )
        is None
    )
