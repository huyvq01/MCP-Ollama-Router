from dataclasses import dataclass


@dataclass(slots=True)
class RoutingRule:
    keywords: set[str]
    capability: str
    priority: int = 100


RULES = [
    RoutingRule(
        keywords={"python", "java", "sql", "bug", "code", "api"},
        capability="code",
        priority=10,
    ),
    RoutingRule(
        keywords={"math", "logic", "reason", "proof"},
        capability="reasoning",
        priority=20,
    ),
    RoutingRule(
        keywords={"image", "vision", "ocr"},
        capability="vision",
        priority=30,
    ),
]