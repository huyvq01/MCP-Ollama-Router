import re

from app.config import MAX_ROUTER_MODEL_B
from app.registry.schemas import ModelMetadata
from app.runtime import runtime


def parameter_billions(model: ModelMetadata) -> float | None:
    """Read parameter metadata first; infer from a size tag as a fallback."""
    metadata = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*([BMT])\s*",
        model.parameter_size,
        re.IGNORECASE,
    )
    if metadata is not None:
        value = float(metadata.group(1))
        scale = {"M": 0.001, "B": 1.0, "T": 1000.0}
        return value * scale[metadata.group(2).upper()]

    # Boundaries prevent matching 3B inside 13B or a size inside a word.
    tags = re.findall(
        r"(?<![\w.])(\d+(?:\.\d+)?)b(?![a-z0-9])",
        model.name,
        re.IGNORECASE,
    )
    if not tags:
        return None
    return max(float(tag) for tag in tags)


def supported(model: ModelMetadata) -> bool:
    size = parameter_billions(model)
    if "embedding" in model.capabilities:
        return False
    return (runtime.allow_unknown_model_size if size is None else size <= MAX_ROUTER_MODEL_B)
