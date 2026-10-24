from dataclasses import dataclass
from enum import Enum
import re

from app.models.message import Message
from app.router.matcher import Capability, Complexity, matcher
from app.router.text import contains_any, normalize


class Task(str, Enum):
    CODE = "code"
    EXPLAIN = "explain"
    DOCUMENTATION = "documentation"
    REASONING = "reasoning"
    GENERAL = "general"


@dataclass(frozen=True)
class TaskProfile:
    task: Task
    capability: Capability
    complexity: Complexity
    max_tokens: int
    temperature: float
    instruction: str
    routing_prompt: str


def analyze(prompt: str, history: list[Message] | None = None) -> TaskProfile:
    routing_prompt = prompt
    text = normalize(prompt)
    followups = (
        "tiep tuc", "viet tiep", "cho vi du", "vi du khac", "chi tiet hon",
        "rut gon", "continue", "another example", "more details", "shorten it",
    )
    if any(text.strip().startswith(term) for term in followups):
        latest_user = None
        for message in reversed(history or []):
            if message["role"] == "user":
                latest_user = latest_user or message["content"]
                if any(
                    normalize(message["content"]).strip().startswith(term)
                    for term in followups
                ):
                    continue
                routing_prompt = message["content"] + "\n" + prompt
                break
        else:
            if latest_user:
                routing_prompt = latest_user + "\n" + prompt

    text = normalize(routing_prompt)
    capability = matcher.match(routing_prompt)
    complexity = matcher.complexity(routing_prompt)
    docs = (
        "tai lieu", "readme", "documentation", "user guide", "huong dan su dung",
        "dac ta", "specification", "write a document", "viet huong dan",
        "bai viet", "technical article",
    )
    implementation = (
        "viet code", "viet ham", "tao ham", "lap trinh", "sua loi", "sua code",
        "toi uu code", "debug", "refactor", "implement", "fix", "write code",
        "write a function", "create an api", "tao api", "stack trace", "traceback",
    )
    explanation = (
        "la gi", "giai thich", "khai niem", "hoat dong nhu the nao", "what is",
        "what are", "explain", "how does", "su khac nhau", "difference between",
        "co che", "nguyen ly", "so sanh",
    )
    technology = (
        "spring", "spring boot", "django", "react", "docker", "kubernetes",
        "database", "co so du lieu", "thuat toan", "ham", "lap trinh",
        "ma nguon", "doan ma", "loi", "unit test", "kiem thu",
    )
    # An implementation command at the beginning wins over incidental
    # mentions of README/documentation in the code's requested behavior.
    leading = re.sub(
        r"^(?:(?:hay|vui long|please|toi muon|can you|ban hay)\s+)+", "", text.strip(),
    )
    starts_implementation = any(leading.startswith(term) for term in implementation)
    starts_implementation = starts_implementation or bool(re.match(
        r"(?:write|create|generate|viet|tao)\s+(?:(?:a|an|mot)\s+)?"
        r"(?:python|java|javascript|typescript|sql|c#|golang)\b", leading,
    ))
    if starts_implementation:
        task, capability = Task.CODE, Capability.CODE
    elif contains_any(text, docs):
        task, capability = Task.DOCUMENTATION, Capability.GENERAL
    elif contains_any(text, implementation):
        task, capability = Task.CODE, Capability.CODE
    elif contains_any(text, explanation):
        task, capability = Task.EXPLAIN, Capability.GENERAL
    elif (
        capability == Capability.CODE or contains_any(text, technology)
        or "```" in routing_prompt
    ):
        task, capability = Task.CODE, Capability.CODE
    elif capability == Capability.REASONING or contains_any(
        text, ("phan tich", "kien truc", "so sanh", "nguyen nhan", "thiet ke"),
    ):
        task, capability = Task.REASONING, Capability.REASONING
    else:
        task = Task.GENERAL

    if contains_any(text, ("kien truc", "toan bo du an", "phan tich sau")):
        complexity = Complexity.HIGH

    instructions = {
        Task.CODE: (
            768, 0.2,
            "Provide correct, focused code with necessary imports. State assumptions, "
            "explain the change briefly, and include a useful usage or test example. "
            "Do not invent APIs or claim code was executed. Prefer a complete small "
            "solution over an unfinished large implementation.",
        ),
        Task.EXPLAIN: (
            384, 0.3,
            "Explain the concept directly in plain language. Include one small "
            "relevant example and important caveats. Avoid a large implementation.",
        ),
        Task.DOCUMENTATION: (
            1024, 0.4,
            "Write structured Markdown documentation suited to the request. Use "
            "clear headings, concrete steps and examples. Mark unknown project "
            "details as assumptions or placeholders; do not invent requirements.",
        ),
        Task.REASONING: (
            768, 0.3,
            "Give the conclusion, supporting reasons, tradeoffs and a practical "
            "recommendation. Distinguish known facts from assumptions.",
        ),
        Task.GENERAL: (
            192, 0.4,
            "Answer directly and concisely. Ask for clarification only when needed.",
        ),
    }
    budget, temperature, instruction = instructions[task]
    if complexity == Complexity.HIGH or contains_any(
        text, ("chi tiet", "day du", "detailed", "comprehensive"),
    ):
        budget = 1536
    if contains_any(normalize(prompt), ("ngan gon", "brief", "concise", "rut gon")):
        budget = min(budget, 256)
    instruction += " Answer in the language of the user's latest question."
    return TaskProfile(
        task, capability, complexity, budget, temperature, instruction, routing_prompt,
    )
