from app.registry.schemas import ModelMetadata
from app.router.plan import RoutingPlan


def make_model(
    name: str,
    priority: int = 100,
) -> ModelMetadata:
    return ModelMetadata(
        provider="ollama",
        name=name,
        capabilities=["general"],
        priority=priority,
    )


def test_empty_plan() -> None:
    plan = RoutingPlan([])

    assert plan.current() is None
    assert plan.next() is None
    assert plan.remaining() == 0


def test_plan_iteration() -> None:
    m1 = make_model("qwen")
    m2 = make_model("deepseek")
    m3 = make_model("gemma")

    plan = RoutingPlan([m1, m2, m3])

    assert plan.current() == m1
    assert plan.remaining() == 3

    assert plan.next() == m2
    assert plan.remaining() == 2

    assert plan.next() == m3
    assert plan.remaining() == 1

    assert plan.next() is None
    assert plan.remaining() == 0

    assert plan.current() is None
