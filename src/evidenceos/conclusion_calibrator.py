from __future__ import annotations
import uuid

from .models import CanonicalClaim, BodyOfEvidence, CertaintyAssessment, CalibratedConclusion


def _phrase(level: str) -> str:
    return {
        "high": "",
        "moderate": "probably ",
        "low": "may ",
        "very_low": "may, but the effect is very uncertain, ",
    }[level]


class ConclusionCalibrator:
    @staticmethod
    def build(claim: CanonicalClaim, body: BodyOfEvidence, certainty: CertaintyAssessment) -> CalibratedConclusion:
        level = certainty.final_level
        phrase = _phrase(level)

        if body.effect_direction == "favours_intervention":
            core = f"{claim.intervention} {phrase}improves {claim.outcome} compared with {claim.comparator}"
        elif body.effect_direction == "favours_comparator":
            core = f"{claim.intervention} {phrase}may be less effective than {claim.comparator} for {claim.outcome}"
        elif body.effect_direction == "no_clear_difference":
            if level in {"high","moderate"}:
                core = f"{claim.intervention} {phrase}has little or no effect on {claim.outcome} compared with {claim.comparator}"
            else:
                core = f"The effect of {claim.intervention} on {claim.outcome} compared with {claim.comparator} is uncertain"
        elif body.effect_direction == "mixed":
            core = f"Evidence on the effect of {claim.intervention} on {claim.outcome} compared with {claim.comparator} is inconsistent"
        else:
            core = f"The effect of {claim.intervention} on {claim.outcome} compared with {claim.comparator} is uncertain"

        text = core.rstrip(".") + "."
        return CalibratedConclusion(
            conclusion_id=f"CONC-{uuid.uuid4().hex[:10].upper()}",
            claim_id=claim.claim_id,
            certainty_id=certainty.certainty_id,
            text=text,
            epistemic_phrase=phrase.strip(),
            certainty_level=level,
        )
