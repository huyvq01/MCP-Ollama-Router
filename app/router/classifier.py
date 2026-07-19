import json

from app.models.selection import ModelSelection
from app.prompts.classifier import CLASSIFIER_PROMPT


class AIClassifier:

    async def classify(
        self,
        provider,
        models: list[str],
        question: str,
    ) -> ModelSelection:

        prompt = CLASSIFIER_PROMPT.format(
            question=question,
            models="\n".join(models),
        )

        answer = await provider.chat(
            model=models[0],
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        try:

            data = json.loads(answer)

            return ModelSelection(**data)

        except Exception:

            return ModelSelection(
                provider="ollama",
                model=models[0],
                reason="fallback",
            )