from app.registry.schemas import ModelMetadata
from app.router.policy import RoutingPolicy


def make_model(
    capabilities: list[str],
    priority: int = 100,
) -> ModelMetadata:
    return ModelMetadata(
        provider="ollama",
        name="test-model",
        capabilities=capabilities,
        priority=priority,
    )


def test_score_matching_capability() -> None:
    policy = RoutingPolicy()

    model = make_model(
        capabilities=["general", "code"],
        priority=80,
    )

    score = policy.score(
        model,
        "code",
    )

    assert score == 180


def test_score_non_matching_capability() -> None:
    policy = RoutingPolicy()

    model = make_model(
        capabilities=["general"],
        priority=80,
    )

    score = policy.score(
        model,
        "code",
    )

    assert score == 80


def test_matching_capability_scores_higher() -> None:
    policy = RoutingPolicy()

    matching = make_model(
        capabilities=["code"],
        priority=80,
    )

    non_matching = make_model(
        capabilities=["general"],
        priority=80,
    )

    assert policy.score(
        matching,
        "code",
    ) > policy.score(
        non_matching,
        "code",
    )


def test_priority_affects_score() -> None:
    policy = RoutingPolicy()

    high_priority = make_model(
        capabilities=["code"],
        priority=100,
    )

    low_priority = make_model(
        capabilities=["code"],
        priority=50,
    )

    assert policy.score(
        high_priority,
        "code",
    ) > policy.score(
        low_priority,
        "code",
    )
