from app.router.rules import RULES


class PromptMatcher:

    def match(
        self,
        prompt: str,
    ) -> str:

        prompt = prompt.lower()

        for rule in RULES:

            if any(
                keyword in prompt
                for keyword in rule.keywords
            ):
                return rule.capability

        return "general"


matcher = PromptMatcher()