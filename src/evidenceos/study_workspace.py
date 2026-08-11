from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field


class StudyWorkspaceRequest(BaseModel):
    record: dict[str, Any]
    design: dict[str, Any]
    eligibility: dict[str, Any]


class AppraisalSignal(BaseModel):
    signal: str
    status: str
    evidence: str | None = None


class StudyWorkspaceResponse(BaseModel):
    record: dict[str, Any]
    design: dict[str, Any]
    eligibility: dict[str, Any]
    appraisal_tool: str
    appraisal_status: str
    readiness_score: int = Field(ge=0, le=100)
    observed_signals: list[AppraisalSignal]
    required_full_text_information: list[str]
    methodological_note: str


def _contains(text: str, patterns: list[str]) -> str | None:
    low = text.lower()
    for p in patterns:
        if p in low:
            return p
    return None


def build_study_workspace(req: StudyWorkspaceRequest) -> StudyWorkspaceResponse:
    record = req.record
    design = req.design
    eligibility = req.eligibility

    title = str(record.get("title") or "")
    abstract = str(record.get("abstract") or "")
    text = f"{title} {abstract}".strip()
    label = str(design.get("final_label") or "uncertain")

    if label == "randomized_controlled_trial":
        tool = "RoB 2"
        required = [
            "Random sequence generation and allocation concealment",
            "Baseline imbalances and randomization integrity",
            "Awareness of intervention assignment and deviations from intended intervention",
            "Outcome-specific missing data and reasons for missingness",
            "Outcome measurement method and assessor awareness",
            "Prespecified analysis plan / trial registration / protocol",
            "Multiplicity of measurements and analyses for the selected outcome",
        ]
    elif label in {"cohort", "case_control", "nonrandomized_intervention"}:
        tool = "ROBINS-I / design-appropriate appraisal"
        required = [
            "Confounding domains and adjustment strategy",
            "Participant selection",
            "Intervention/exposure classification",
            "Deviations from intended intervention",
            "Missing data",
            "Outcome measurement",
            "Selective reporting",
        ]
    elif label in {"systematic_review", "meta_analysis"}:
        tool = "AMSTAR 2 / review-appropriate appraisal"
        required = [
            "Protocol registration",
            "Search strategy and databases",
            "Study selection and extraction methods",
            "Risk-of-bias methods",
            "Meta-analytic methods where applicable",
            "Publication-bias assessment",
            "Interpretation in light of study limitations",
        ]
    else:
        tool = "Design-appropriate critical appraisal"
        required = [
            "Full methods section",
            "Participant selection",
            "Exposure/intervention details",
            "Outcome measurement",
            "Missing data",
            "Analysis plan",
            "Selective reporting safeguards",
        ]

    signals = []

    randomized = _contains(text, ["randomized", "randomised", "randomly assigned"])
    signals.append(AppraisalSignal(
        signal="Randomization explicitly mentioned",
        status="observed" if randomized else "not_observed",
        evidence=randomized,
    ))

    blinded = _contains(text, ["double-blind", "double blind", "single-blind", "single blind", "blinded"])
    signals.append(AppraisalSignal(
        signal="Blinding explicitly mentioned",
        status="observed" if blinded else "not_observed",
        evidence=blinded,
    ))

    registered = _contains(text, ["clinicaltrials.gov", "trial registration", "registered", "nct"])
    signals.append(AppraisalSignal(
        signal="Registration/protocol signal",
        status="observed" if registered else "not_observed",
        evidence=registered,
    ))

    attrition = _contains(text, ["lost to follow-up", "lost to followup", "dropout", "attrition", "withdraw"])
    signals.append(AppraisalSignal(
        signal="Attrition/missing-data signal",
        status="observed" if attrition else "not_observed",
        evidence=attrition,
    ))

    itt = _contains(text, ["intention-to-treat", "intention to treat", "intent-to-treat", "itt analysis"])
    signals.append(AppraisalSignal(
        signal="Intention-to-treat signal",
        status="observed" if itt else "not_observed",
        evidence=itt,
    ))

    has_abstract = bool(abstract.strip())
    has_pmid = bool(record.get("pmid"))
    has_doi = bool(record.get("doi"))
    has_pubtypes = bool(record.get("publication_types"))

    completeness = sum([has_abstract, has_pmid, has_doi, has_pubtypes])
    readiness = 15 + completeness * 8 + sum(5 for s in signals if s.status == "observed")
    readiness = min(readiness, 55)

    return StudyWorkspaceResponse(
        record=record,
        design=design,
        eligibility=eligibility,
        appraisal_tool=tool,
        appraisal_status="full_text_required",
        readiness_score=readiness,
        observed_signals=signals,
        required_full_text_information=required,
        methodological_note=(
            "Abstract-level signals are not risk-of-bias judgements. "
            "EvidenceOS will not assign a RoB 2 domain judgement until the relevant "
            "full-text information and outcome context are available."
        ),
    )
