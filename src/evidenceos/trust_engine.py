from __future__ import annotations

from pydantic import BaseModel, Field

from .extraction_engine import ExtractionEngine
from .rob2_engine import RoB2Engine


class TrustAssessment(BaseModel):
    applicable: bool
    framework: str
    status: str
    headline: str
    explanation: str
    outcome_assessments: list[dict] = Field(default_factory=list)


def assess_full_text(report_id: str, title: str, text: str) -> TrustAssessment:
    extraction = ExtractionEngine().extract(report_id, title, text)

    randomized = any(
        f.field_name == "randomization_reported" and f.value is True
        for f in extraction.methodological_fields
    )

    if not randomized:
        return TrustAssessment(
            applicable=False,
            framework="RoB 2",
            status="not_applicable",
            headline="RoB 2 not activated",
            explanation=(
                "EvidenceOS did not verify that this report is a randomized trial. "
                "A design-appropriate appraisal framework is required."
            ),
        )

    engine = RoB2Engine()
    assessments = []

    if extraction.outcomes:
        for result in extraction.outcomes:
            rob = engine.assess(extraction, result_id=result.result_id)
            assessments.append({
                "result_id": result.result_id,
                "outcome": result.outcome_name,
                "timepoint": result.timepoint,
                "effect_measure": result.effect_measure,
                "overall_judgement": rob.overall_judgement,
                "overall_rationale": rob.overall_rationale,
                "domains": [
                    {
                        "domain_id": d.domain_id,
                        "domain_name": d.domain_name,
                        "judgement": d.judgement,
                        "rationale": d.rationale,
                        "source_span_ids": d.source_span_ids,
                    }
                    for d in rob.domains
                ],
            })
    else:
        rob = engine.assess(extraction, result_id=None)
        assessments.append({
            "result_id": None,
            "outcome": "Outcome not deterministically mapped",
            "timepoint": None,
            "effect_measure": None,
            "overall_judgement": rob.overall_judgement,
            "overall_rationale": rob.overall_rationale,
            "domains": [
                {
                    "domain_id": d.domain_id,
                    "domain_name": d.domain_name,
                    "judgement": d.judgement,
                    "rationale": d.rationale,
                    "source_span_ids": d.source_span_ids,
                }
                for d in rob.domains
            ],
        })

    unresolved = all(
        a["overall_judgement"] == "unresolved"
        for a in assessments
    )

    return TrustAssessment(
        applicable=True,
        framework="RoB 2",
        status="preliminary_full_text_assistance",
        headline=(
            "Methodological appraisal requires human verification"
            if unresolved
            else "Preliminary RoB 2 assistance available"
        ),
        explanation=(
            "EvidenceOS applies deterministic signalling rules to the uploaded full text. "
            "These are outcome-specific decision-support outputs, not a final validated "
            "risk-of-bias assessment. NI/unresolved responses are preserved rather than guessed."
        ),
        outcome_assessments=assessments,
    )
