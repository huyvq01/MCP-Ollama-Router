CLASSIFIER_PROMPT = """
You are an AI routing engine.

Your task is to select the most suitable model.

Rules:
- Return ONLY valid JSON.
- Never explain.
- Never answer the user.

JSON format:

{{
    "provider": "ollama",
    "model": "model-name"
}}

Question:
{question}

Available models:
{models}
""".strip()