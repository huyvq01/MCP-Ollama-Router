from enum import Enum

from app.router.text import contains_any, normalize

from app.router.rules import (
    CODE,
    COMPLEXITY,
    REASONING,
    VISION,
)


class Capability(str, Enum):
    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelMatcher:
    def match(
        self,
        prompt: str,
    ) -> Capability:
        text = normalize(prompt)

        if contains_any(text, CODE):
            return Capability.CODE

        if contains_any(text, REASONING):
            return Capability.REASONING

        if contains_any(text, VISION):
            return Capability.VISION

        return Capability.GENERAL

    def capability(
        self,
        prompt: str,
    ) -> Capability:
        return self.match(prompt)

    def complexity(
        self,
        prompt: str,
    ) -> Complexity:
        text = normalize(prompt)

        if contains_any(text, COMPLEXITY):
            return Complexity.HIGH

        if len(prompt) > 12000:
            return Complexity.HIGH

        if len(prompt) > 4000:
            return Complexity.MEDIUM

        return Complexity.LOW


matcher = ModelMatcher()
