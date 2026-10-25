import re
from enum import StrEnum


class Capability(StrEnum):
    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"
    TRANSLATION = "translation"
    SUMMARIZE = "summarize"
    REPORT = "report"


class PromptMatcher:
    RULES = (
        (Capability.TRANSLATION, ("translate", "dịch")),
        (Capability.SUMMARIZE, ("summarize", "tóm tắt", "summary")),
        (Capability.REPORT, ("report", "báo cáo", "dàn ý", "luận văn", "thuyết minh")),
        (Capability.VISION, ("image", "photo", "picture", "ocr", "hình ảnh")),
        (
            Capability.CODE,
            (
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
                "javascript",
                "typescript",
                "docker",
                "git",
                "microflow",
                "nanoflow",
                "lập trình",
                "sửa lỗi",
            ),
        ),
        (
            Capability.REASONING,
            (
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
                "giải thích",
                "phân tích",
            ),
        ),
    )

    def match(self, prompt: str) -> Capability:
        text = prompt.casefold()
        for capability, words in self.RULES:
            if any(
                re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text) for w in words
            ):
                return capability
        return Capability.GENERAL


matcher = PromptMatcher()
