from __future__ import annotations
import uuid

from .models import GapHypothesis, GapFalsificationAssessment, FinalGap, ResearchOpportunity


DESIGN_MAP = {
    "quantity": "randomized_trial",
    "quality": "methodological_study",
    "precision": "randomized_trial",
    "consistency": "methodological_study",
    "population": "cohort",
    "intervention": "randomized_trial",
    "comparator": "randomized_trial",
    "outcome": "cohort",
    "temporal": "cohort",
    "implementation": "implementation_study",
    "experience": "qualitative_study",
    "replication": "replication_study",
    "construct": "methodological_study",
    "unknown": "uncertain",
}


class ResearchOpportunityEngine:
    @staticmethod
    def final_gap(gap: GapHypothesis, fals: GapFalsificationAssessment) -> FinalGap:
        if fals.verdict == "rejected":
            statement = f"The original gap hypothesis was not supported: {gap.statement}"
            types = []
        elif fals.verdict == "refined":
            statement = f"A narrower unresolved issue may remain: {gap.statement}"
            types = fals.final_gap_type or [gap.initial_gap_type]
        else:
            statement = gap.statement
            types = fals.final_gap_type or [gap.initial_gap_type]

        return FinalGap(
            final_gap_id=f"FG-{uuid.uuid4().hex[:10].upper()}",
            source_gap_hypothesis_id=gap.gap_hypothesis_id,
            statement=statement,
            gap_types=types,
            confidence=fals.confidence,
            status=fals.verdict,
            verification_note=fals.rationale,
        )

    @staticmethod
    def opportunity(final_gap: FinalGap) -> ResearchOpportunity | None:
        if final_gap.status == "rejected":
            return None

        primary_type = final_gap.gap_types[0] if final_gap.gap_types else "unknown"
        design = DESIGN_MAP.get(primary_type, "uncertain")

        return ResearchOpportunity(
            opportunity_id=f"OPP-{uuid.uuid4().hex[:10].upper()}",
            final_gap_id=final_gap.final_gap_id,
            suggested_design=design,
            proposed_question=f"What study could directly address: {final_gap.statement}",
            rationale=f"The gap was classified primarily as '{primary_type}' with {final_gap.confidence} confidence.",
            caution="This is a research direction, not a recommendation to conduct a study without a dedicated novelty and feasibility assessment.",
        )
