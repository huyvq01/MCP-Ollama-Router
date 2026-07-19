from app.models.provider import ModelInfo

MODELS = [
    ModelInfo(
        provider="ollama",
        name="qwen2.5-coder:7b",
        capabilities=["code", "python", "java", "sql"],
        priority=10,
    ),
    ModelInfo(
        provider="ollama",
        name="deepseek-r1:8b",
        capabilities=["reasoning", "math"],
        priority=20,
    ),
    ModelInfo(
        provider="ollama",
        name="llama3.1:8b",
        capabilities=["general"],
        priority=50,
    ),
]