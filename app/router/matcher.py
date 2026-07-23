from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"
    TRANSLATION = "translation"
    SUMMARIZE = "summarize"


class PromptMatcher:
    CODE_KEYWORDS = (
        "code",
        "python",
        "java",
        "c#",
        "golang",
        "go",
        "rust",
        "bug",
        "fix",
        "refactor",
        "sql",
        "api",
        "fastapi",
        "javascript",
        "typescript",
        "docker",
        "git",
    )

    REASONING_KEYWORDS = (
        "explain",
        "reason",
        "logic",
        "algorithm",
        "math",
        "optimize",
        "analysis",
        "why",
        "prove",
        "solve",
    )

    VISION_KEYWORDS = (
        "image",
        "photo",
        "picture",
        "vision",
        "describe image",
        "ocr",
        "detect",
        "recognize",
    )

    TRANSLATION_KEYWORDS = (
        "translate",
        "dịch",
    )

    SUMMARIZE_KEYWORDS = (
        "summarize",
        "tóm tắt",
        "summary",
    )

    def match(self, prompt: str) -> Capability:
        text = prompt.lower()

        if any(word in text for word in self.CODE_KEYWORDS):
            return Capability.CODE

        if any(word in text for word in self.REASONING_KEYWORDS):
            return Capability.REASONING

        if any(word in text for word in self.VISION_KEYWORDS):
            return Capability.VISION

        if any(word in text for word in self.TRANSLATION_KEYWORDS):
            return Capability.TRANSLATION

        if any(word in text for word in self.SUMMARIZE_KEYWORDS):
            return Capability.SUMMARIZE

        return Capability.GENERAL


matcher = PromptMatcher()
