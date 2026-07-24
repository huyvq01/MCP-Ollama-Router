from app.router.rules import CODE, GENERAL, REASONING, VISION


def test_code_rules() -> None:
    assert "python" in CODE
    assert "java" in CODE
    assert "rust" in CODE
    assert "typescript" in CODE
    assert "sql" in CODE


def test_reasoning_rules() -> None:
    assert "math" in REASONING
    assert "logic" in REASONING
    assert "reason" in REASONING
    assert "analysis" in REASONING


def test_vision_rules() -> None:
    assert "image" in VISION
    assert "ocr" in VISION
    assert "picture" in VISION
    assert "photo" in VISION


def test_general_rules() -> None:
    assert GENERAL == []
