from app.registry.schemas import ModelMetadata
from app.router.matcher import Capability, Complexity


class RoutingPolicy:
    """
    Routing policy optimized for a 16 GB RAM CPU-only machine.

    Base scoring remains backward compatible:

        Matching capability:
            100 + priority

        Non-matching capability:
            priority
    """

    def score(
        self,
        model: ModelMetadata,
        capability: Capability | str,
        complexity: Complexity | str = Complexity.LOW,
    ) -> int:
        capability_value = (
            capability.value
            if isinstance(capability, Capability)
            else capability
        )

        complexity_value = (
            complexity.value
            if isinstance(complexity, Complexity)
            else complexity
        )

        # ----------------------------------------------------
        # Base capability score.
        # ----------------------------------------------------

        if capability_value in model.capabilities:
            score = 100 + model.priority
        else:
            score = model.priority

        # ----------------------------------------------------
        # Complexity-aware model preference.
        # ----------------------------------------------------

        if complexity_value == Complexity.LOW.value:
            # Prefer 3B and smaller models for simple requests.
            if self._is_light_model(model):
                score += 10

        elif complexity_value == Complexity.MEDIUM.value:
            # Still prefer small models, but less aggressively.
            if self._is_light_model(model):
                score += 5

        elif complexity_value == Complexity.HIGH.value:
            # Prefer 7B/8B-class models for complex requests.
            if self._is_medium_model(model):
                score += 10

        return score

    @staticmethod
    def _model_size(
        model: ModelMetadata,
    ) -> float:
        """
        Extract approximate parameter size from model name.

        Examples:
            qwen2.5-coder:3b -> 3
            qwen2.5-coder:7b -> 7
            deepseek-r1:14b  -> 14
        """

        name = model.name.lower()

        known_sizes = (
            "0.5b",
            "1b",
            "1.5b",
            "3b",
            "7b",
            "8b",
            "12b",
            "14b",
            "20b",
            "27b",
            "32b",
            "34b",
            "70b",
        )

        for size in known_sizes:
            if size in name:
                try:
                    return float(size[:-1])
                except ValueError:
                    return 999.0

        # Unknown size is treated as large.
        return 999.0

    @classmethod
    def _is_light_model(
        cls,
        model: ModelMetadata,
    ) -> bool:
        """
        3B or smaller.
        """

        return cls._model_size(model) <= 3

    @classmethod
    def _is_medium_model(
        cls,
        model: ModelMetadata,
    ) -> bool:
        """
        >3B and <=8B.
        """

        size = cls._model_size(model)

        return 3 < size <= 8

    @classmethod
    def _is_strong_model(
        cls,
        model: ModelMetadata,
    ) -> bool:
        """
        >8B.

        Kept for compatibility with existing code/tests.
        """

        return cls._model_size(model) > 8