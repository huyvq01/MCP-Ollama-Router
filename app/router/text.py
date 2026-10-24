import re
import unicodedata
from collections.abc import Iterable


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(char for char in text if not unicodedata.combining(char))


def contains_any(text: str, terms: Iterable[str]) -> bool:
    """Match words/phrases, so 'go' does not match 'google'."""
    return any(
        re.search(r"(?<!\w)" + re.escape(normalize(term)) + r"(?!\w)", text)
        for term in terms
    )
