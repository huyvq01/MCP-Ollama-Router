from app.models.provider import ModelInfo


class ModelClassifier:
    def classify(self, model: str) -> ModelInfo:
        lower = model.lower()

        capabilities = ["general"]
        priority = 80

        if "coder" in lower:
            capabilities = ["code", "chat"]
            priority = 100

        elif "deepseek" in lower:
            capabilities = ["reasoning", "math"]
            priority = 95

        elif "llava" in lower:
            capabilities = ["vision"]
            priority = 90

        elif "gemma" in lower:
            capabilities = ["general"]
            priority = 85

        elif "llama" in lower:
            capabilities = ["general"]
            priority = 90

        return ModelInfo(
            provider="ollama",
            name=model,
            capabilities=capabilities,
            priority=priority,
        )
