from app.router.rules import *


class ModelMatcher:

    def capability(
        self,
        prompt: str,
    ) -> str:

        text = prompt.lower()

        for keyword in CODE:

            if keyword in text:
                return "code"

        for keyword in REASONING:

            if keyword in text:
                return "reasoning"

        for keyword in VISION:

            if keyword in text:
                return "vision"

        return "general"


matcher = ModelMatcher()