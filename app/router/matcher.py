from enum import Enum

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
        text = prompt.lower()

        for keyword in CODE:
            if keyword in text:
                return Capability.CODE

        for keyword in REASONING:
            if keyword in text:
                return Capability.REASONING

        for keyword in VISION:
            if keyword in text:
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
        text = prompt.lower()

        for keyword in COMPLEXITY:
            if keyword in text:
                return Complexity.HIGH

        if len(prompt) > 12000:
            return Complexity.HIGH

        if len(prompt) > 4000:
            return Complexity.MEDIUM

        return Complexity.LOW


matcher = ModelMatcher()