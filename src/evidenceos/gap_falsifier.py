from __future__ import annotations
import uuid

from .models import GapHypothesis, GapEvidence, GapFalsificationAssessment, BodyOfEvidence, CanonicalClaim


class GapFalsifier:
    """
    v0.8 corpus-level falsification.

    It tries to disprove a gap using evidence already represented in the topic.
    External adversarial search comes next.
    """

    @staticmethod
    def build_evidence(
        gap: GapHypothesis,
        bodies: list[BodyOfEvidence],
        claims: list[CanonicalClaim],
    ) -> list[GapEvidence]:
        out = []
        detected = set(gap.detected_from)

        for b in bodies:
            if b.body_id in detected or any(rid in detected for rid in b.result_ids):
                supports = True
                rationale = "This body of evidence contributed to the initial gap hypothesis."
                if gap.initial_gap_type == "quantity" and b.unique_studies >= 3:
                    supports = False
                    rationale = "The available body includes multiple studies, weakening a simple quantity-gap claim."
                elif gap.initial_gap_type == "precision" and b.total_participants is not None and b.total_participants >= 800:
                    supports = False
                    rationale = "The total sample is substantial, weakening a simple precision-gap claim."
                out.append(GapEvidence(
                    evidence_id=f"GE-{uuid.uuid4().hex[:10].upper()}",
                    gap_hypothesis_id=gap.gap_hypothesis_id,
                    source_type="body_of_evidence",
                    source_id=b.body_id,
                    supports_gap=supports,
                    directness="direct",
                    rationale=rationale,
                ))

        return out

    @staticmethod
    def assess(
        gap: GapHypothesis,
        evidence: list[GapEvidence],
        construct_ambiguity: str = "low",
    ) -> GapFalsificationAssessment:
        direct_support = [e for e in evidence if e.supports_gap and e.directness=="direct"]
        direct_against = [e for e in evidence if (not e.supports_gap) and e.directness=="direct"]

        if direct_against and not direct_support:
            verdict = "rejected"
            rationale = "Direct corpus evidence contradicts the original gap hypothesis."
            confidence = "high"
            final_types = []
        elif direct_against and direct_support:
            verdict = "refined"
            rationale = "The original gap statement is too broad; corpus evidence supports a narrower formulation."
            confidence = "moderate"
            final_types = [gap.initial_gap_type]
        elif direct_support:
            verdict = "verified" if construct_ambiguity != "high" else "refined"
            rationale = (
                "The corpus supports the gap hypothesis."
                if verdict=="verified"
                else "The corpus supports a gap, but construct ambiguity requires a narrower formulation."
            )
            confidence = "moderate"
            final_types = [gap.initial_gap_type]
        else:
            verdict = "unresolved"
            rationale = "The available corpus is insufficient to verify or falsify the gap."
            confidence = "low"
            final_types = [gap.initial_gap_type]

        return GapFalsificationAssessment(
            falsification_id=f"FALS-{uuid.uuid4().hex[:10].upper()}",
            gap_hypothesis_id=gap.gap_hypothesis_id,
            verdict=verdict,
            rationale=rationale,
            evidence_ids=[e.evidence_id for e in evidence],
            final_gap_type=final_types,
            confidence=confidence,
        )
