CLASSIFIER_PROMPT = """
You are a routing model.

Choose the best model.

Available models:

{models}

Question:

{question}

Answer only model name.
""".strip()
