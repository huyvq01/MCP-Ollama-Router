from app.router.classifier import ModelClassifier

classifier = ModelClassifier()


def test_qwen_coder() -> None:
    model = classifier.classify("qwen2.5-coder:7b")

    assert model.provider == "ollama"
    assert model.priority == 100
    assert "code" in model.capabilities
    assert "chat" in model.capabilities


def test_deepseek() -> None:
    model = classifier.classify("deepseek-r1:14b")

    assert model.priority == 95
    assert "reasoning" in model.capabilities
    assert "math" in model.capabilities


def test_llava() -> None:
    model = classifier.classify("llava:latest")

    assert model.priority == 90
    assert model.capabilities == ["vision"]


def test_gemma() -> None:
    model = classifier.classify("gemma3:12b")

    assert model.priority == 85
    assert model.capabilities == ["general"]


def test_llama() -> None:
    model = classifier.classify("llama3")

    assert model.priority == 90
    assert model.capabilities == ["general"]


def test_unknown_model() -> None:
    model = classifier.classify("my-custom-model")

    assert model.priority == 80
    assert model.capabilities == ["general"]
