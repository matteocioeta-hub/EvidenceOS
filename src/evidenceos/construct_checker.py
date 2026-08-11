from __future__ import annotations
import uuid
from .models import GapHypothesis, ConstructCheck

AMBIGUOUS = {
    "adherence": [
        "dropout",
        "attendance",
        "protocol completion",
        "exercise dose completed",
        "long-term maintenance",
        "habitual physical activity"
    ],
    "function": [
        "self-reported disability",
        "performance-based function",
        "participation"
    ],
    "quality of life": [
        "generic health-related quality of life",
        "condition-specific impact",
        "global health"
    ],
}

class ConstructChecker:
    @staticmethod
    def check(gap: GapHypothesis) -> ConstructCheck:
        term = gap.topic.strip().lower()
        candidates = []
        ambiguity = "low"
        rationale = "No major predefined construct ambiguity detected."

        for key, values in AMBIGUOUS.items():
            if key in term or key in gap.statement.lower():
                candidates = values
                ambiguity = "high"
                rationale = f"The term '{key}' can represent materially different constructs."
                break

        return ConstructCheck(
            construct_check_id=f"CONST-{uuid.uuid4().hex[:10].upper()}",
            gap_hypothesis_id=gap.gap_hypothesis_id,
            input_term=gap.topic,
            ambiguity=ambiguity,
            candidate_constructs=candidates,
            rationale=rationale,
        )
