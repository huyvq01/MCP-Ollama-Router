from app.router.matcher import Capability, matcher


def test_code() -> None:
    assert matcher.match("write python code") == Capability.CODE


def test_reasoning() -> None:
    assert matcher.match("solve math") == Capability.REASONING


def test_vision() -> None:
    assert matcher.match("describe image") == Capability.VISION


def test_general() -> None:
    assert matcher.match("hello") == Capability.GENERAL
