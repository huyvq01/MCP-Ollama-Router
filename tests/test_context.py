from app.router.context import RouterContext


def test_context_create() -> None:
    context = RouterContext()

    assert context.history is not None
    assert context.cache is not None
    assert context.session is not None


def test_context_instances_are_independent() -> None:
    ctx1 = RouterContext()
    ctx2 = RouterContext()

    assert ctx1 is not ctx2

    assert ctx1.history is not ctx2.history
    assert ctx1.cache is not ctx2.cache
    assert ctx1.session is not ctx2.session
