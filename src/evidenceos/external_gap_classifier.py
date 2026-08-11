from __future__ import annotations
import re
import uuid

from .models import StructuredQuestion, GapHypothesis, ConstructCheck, CanonicalRecord, ExternalGapEvidence


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (s or "").lower())).strip()


def _contains(text: str, term: str) -> bool:
    return _norm(term) in _norm(text)


class ExternalGapEvidenceClassifier:
    @staticmethod
    def classify(
        question: StructuredQuestion,
        gap: GapHypothesis,
        construct_check: ConstructCheck | None,
        record: CanonicalRecord,
    ) -> ExternalGapEvidence:
        text = " ".join([record.title or "", record.abstract or ""])
        pop = _contains(text, question.population.label) or any(
            _contains(text, c) for c in question.population.concepts
        )
        inter = _contains(text, question.intervention.label) or any(
            _contains(text, c) for c in question.intervention.concepts
        )

        constructs = [gap.topic]
        if construct_check and construct_check.candidate_constructs:
            constructs += construct_check.candidate_constructs
        construct_match = any(_contains(text, c) for c in constructs if c)

        gap_specific = False
        if gap.initial_gap_type == "temporal":
            gap_specific = any(x in _norm(text) for x in ["long term","long-term","follow up","follow-up","maintenance","sustained"])
        elif gap.initial_gap_type == "comparator":
            gap_specific = any(x in _norm(text) for x in ["comparative","versus","vs ","head to head","head-to-head"])
        elif gap.initial_gap_type == "quantity":
            gap_specific = any(x in _norm(text) for x in ["systematic review","meta analysis","meta-analysis","randomized trial","randomised trial"])
        elif gap.initial_gap_type == "implementation":
            gap_specific = any(x in _norm(text) for x in ["adherence","implementation","barrier","facilitator","maintenance"])
        else:
            gap_specific = construct_match

        if pop and inter and construct_match and gap_specific:
            directness = "direct"
            relation = "against_gap"
            rationale = "Record directly addresses the population/intervention and the proposed gap construct."
        elif pop and inter and (construct_match or gap_specific):
            directness = "partial"
            relation = "against_gap"
            rationale = "Record addresses the core population/intervention and a closely related gap construct."
        elif construct_match or gap_specific:
            directness = "indirect"
            relation = "uncertain"
            rationale = "Record is related to the gap construct but not clearly direct to the full question."
        else:
            directness = "indirect"
            relation = "uncertain"
            rationale = "Record does not clearly address the proposed gap."

        return ExternalGapEvidence(
            external_evidence_id=f"EGE-{uuid.uuid4().hex[:10].upper()}",
            gap_hypothesis_id=gap.gap_hypothesis_id,
            record_id=record.record_id,
            title=record.title,
            database_sources=record.source_databases,
            directness=directness,
            relation_to_gap=relation,
            rationale=rationale,
            doi=record.doi,
            pmid=record.pmid,
            year=record.year,
        )
