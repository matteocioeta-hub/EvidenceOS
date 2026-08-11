from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from .models import SearchStrategy
from .pubmed_client import PubMedClient


Direction = Literal[
    "favours_intervention",
    "favours_comparator",
    "no_clear_difference",
    "mixed",
    "uncertain",
]


class ConclusionChallengeRequest(BaseModel):
    outcome: str = Field(min_length=1)
    dominant_direction: Direction
    directions: dict[str, int] = Field(default_factory=dict)
    studies_in_body: int = Field(default=1, ge=1)
    methodological_support: str = "insufficiently_characterized"
    population: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    comparator: str = ""
    timepoint: str = ""
    max_results: int = Field(default=15, ge=5, le=20)


class ChallengeDimension(BaseModel):
    dimension: str
    triggered: bool
    severity: Literal["none", "minor", "material", "critical", "unresolved"]
    rationale: str


class ExternalChallengeRecord(BaseModel):
    record_id: str
    title: str
    year: int | None = None
    journal: str | None = None
    pmid: str | None = None
    doi: str | None = None
    relevance: Literal["direct", "partial", "indirect"]
    challenge_signal: Literal[
        "potentially_contradictory",
        "potentially_supportive",
        "neutral_or_unclear",
    ]
    evidence_level: Literal["evidence_synthesis", "trial", "observational", "other"]
    rationale: str


class ConclusionChallengeResponse(BaseModel):
    original_conclusion: str
    verdict: Literal[
        "survived",
        "survived_with_qualification",
        "materially_weakened",
        "unresolved",
    ]
    revised_conclusion: str
    dimensions: list[ChallengeDimension]
    external_query: str
    records_examined: int
    potential_contradictions: int
    higher_level_challenges: int
    records: list[ExternalChallengeRecord]
    interpretation_boundary: str


STOP = {
    "adult", "adults", "people", "persons", "patients", "patient", "with",
    "the", "and", "for", "from", "into", "study", "studies", "effect",
    "effects", "therapy", "treatment",
}


def _tokens(value: str) -> list[str]:
    return [
        x.lower()
        for x in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", value or "")
        if x.lower() not in STOP
    ]


def _concept_group(value: str) -> str:
    clean = (value or "").strip().strip('"')
    if not clean:
        return ""
    items = [f'"{clean}"' if " " in clean else clean]
    for token in _tokens(clean)[:4]:
        quoted = f'"{token}"'
        if quoted not in items:
            items.append(quoted)
    return "(" + " OR ".join(items) + ")"


def _overlap(text: str, concept: str) -> bool:
    toks = _tokens(concept)
    if not toks:
        return False
    low = text.lower()
    hits = sum(t in low for t in toks)
    return hits >= max(1, min(2, len(toks)))


def _original_conclusion(req: ConclusionChallengeRequest) -> str:
    prefix = "In the currently analysed corpus"
    comp = f" compared with {req.comparator}" if req.comparator.strip() else ""
    if req.dominant_direction == "favours_intervention":
        return f"{prefix}, results for {req.outcome} tend to favour {req.intervention}{comp}."
    if req.dominant_direction == "favours_comparator":
        return f"{prefix}, results for {req.outcome} tend to favour the comparator over {req.intervention}."
    if req.dominant_direction == "no_clear_difference":
        return f"{prefix}, results do not show a clear directional difference for {req.outcome}{comp}."
    if req.dominant_direction == "mixed":
        return f"{prefix}, evidence for {req.outcome} is inconsistent."
    return f"{prefix}, the direction of evidence for {req.outcome} remains uncertain."


def _build_query(req: ConclusionChallengeRequest) -> str:
    core = [
        _concept_group(req.population),
        _concept_group(req.intervention),
        _concept_group(req.outcome),
    ]
    if req.comparator.strip():
        core.append(_concept_group(req.comparator))

    challenge_terms = (
        '("systematic review" OR "meta-analysis" OR "randomized controlled trial" '
        'OR "randomised controlled trial" OR "clinical trial" OR comparative '
        'OR "follow-up" OR "long-term")'
    )
    return " AND ".join(x for x in core if x) + " AND " + challenge_terms


def _evidence_level(record) -> str:
    pubs = " ".join(record.publication_types or []).lower()
    title = (record.title or "").lower()
    if "meta-analysis" in pubs or "systematic review" in pubs or "meta-analysis" in title or "systematic review" in title:
        return "evidence_synthesis"
    if (
        "randomized controlled trial" in pubs
        or "clinical trial" in pubs
        or "randomized" in title
        or "randomised" in title
    ):
        return "trial"
    if any(x in pubs for x in ["observational study", "cohort", "case-control"]):
        return "observational"
    return "other"


POSITIVE = [
    r"\bsignificantly improved\b",
    r"\bsignificant improvement\b",
    r"\bwas superior\b",
    r"\bsuperior to\b",
    r"\beffective in\b",
    r"\breduced (?:pain|symptoms|disability)\b",
    r"\bgreater improvement\b",
    r"\bbenefit\b",
]
NULL_NEGATIVE = [
    r"\bno significant difference\b",
    r"\bnot significantly different\b",
    r"\bdid not improve\b",
    r"\bno benefit\b",
    r"\bnot superior\b",
    r"\bineffective\b",
    r"\bno clear difference\b",
    r"\bfailed to improve\b",
]
WORSE = [
    r"\binferior to\b",
    r"\bworse than\b",
    r"\bfavou?rs? (?:the )?control\b",
]


def _pattern_hit(text: str, pats: list[str]) -> bool:
    return any(re.search(p, text, flags=re.I) for p in pats)


def _challenge_signal(text: str, dominant: str) -> str:
    positive = _pattern_hit(text, POSITIVE)
    nullneg = _pattern_hit(text, NULL_NEGATIVE)
    worse = _pattern_hit(text, WORSE)

    if dominant == "favours_intervention":
        if nullneg or worse:
            return "potentially_contradictory"
        if positive:
            return "potentially_supportive"
    elif dominant == "no_clear_difference":
        if positive or worse:
            return "potentially_contradictory"
        if nullneg:
            return "potentially_supportive"
    elif dominant == "favours_comparator":
        if positive:
            return "potentially_contradictory"
        if worse:
            return "potentially_supportive"

    return "neutral_or_unclear"


def _classify(req: ConclusionChallengeRequest, record) -> ExternalChallengeRecord:
    text = f"{record.title or ''}\n{record.abstract or ''}"
    p = _overlap(text, req.population)
    i = _overlap(text, req.intervention)
    o = _overlap(text, req.outcome)
    c = True if not req.comparator.strip() else _overlap(text, req.comparator)

    if p and i and o and c:
        relevance = "direct"
        rel_reason = "Matches the requested population, intervention, outcome and comparator concepts."
    elif p and i and o:
        relevance = "partial"
        rel_reason = "Matches population, intervention and outcome but comparator alignment is incomplete."
    elif p and i:
        relevance = "partial"
        rel_reason = "Matches the core population/intervention but outcome alignment is incomplete."
    else:
        relevance = "indirect"
        rel_reason = "Retrieved by the adversarial query but does not sufficiently match the conclusion context."

    signal = _challenge_signal(text, req.dominant_direction)
    level = _evidence_level(record)
    return ExternalChallengeRecord(
        record_id=record.record_id,
        title=record.title,
        year=record.year,
        journal=record.journal,
        pmid=record.pmid,
        doi=record.doi,
        relevance=relevance,
        challenge_signal=signal,
        evidence_level=level,
        rationale=rel_reason,
    )


def challenge_conclusion(
    req: ConclusionChallengeRequest,
    pubmed: PubMedClient | None = None,
) -> ConclusionChallengeResponse:
    conclusion = _original_conclusion(req)
    dimensions: list[ChallengeDimension] = []

    # 1) Internal contradiction.
    dirs = {k: v for k, v in req.directions.items() if k != "uncertain" and v > 0}
    opposing = False
    if req.dominant_direction == "favours_intervention":
        opposing = any(dirs.get(x, 0) for x in ["favours_comparator", "no_clear_difference"])
    elif req.dominant_direction == "favours_comparator":
        opposing = any(dirs.get(x, 0) for x in ["favours_intervention", "no_clear_difference"])
    elif req.dominant_direction == "no_clear_difference":
        opposing = any(dirs.get(x, 0) for x in ["favours_intervention", "favours_comparator"])
    elif req.dominant_direction == "mixed":
        opposing = True

    dimensions.append(ChallengeDimension(
        dimension="internal_contradictory_evidence",
        triggered=opposing,
        severity="material" if opposing else "none",
        rationale=(
            "The stored body contains results that do not support the dominant direction."
            if opposing
            else "No internal directional contradiction was detected in the stored body."
        ),
    ))

    # 2) Thin evidence base.
    thin = req.studies_in_body <= 2
    dimensions.append(ChallengeDimension(
        dimension="thin_evidence_base",
        triggered=thin,
        severity="material" if req.studies_in_body == 1 else ("minor" if thin else "none"),
        rationale=(
            f"Only {req.studies_in_body} analysed study/studies contribute to this outcome."
            if thin
            else f"{req.studies_in_body} analysed studies contribute to this outcome."
        ),
    ))

    # 3) Methodological support.
    weak_method = req.methodological_support == "insufficiently_characterized"
    dimensions.append(ChallengeDimension(
        dimension="methodological_uncertainty",
        triggered=weak_method,
        severity="material" if weak_method else "none",
        rationale=(
            "Methodological trust is insufficiently characterized across contributing studies."
            if weak_method
            else f"Methodological support is currently classified as {req.methodological_support}."
        ),
    ))

    # External adversarial PubMed search.
    query = _build_query(req)
    strategy = SearchStrategy(
        strategy_id=f"CHAL-{uuid.uuid4().hex[:10].upper()}",
        question_id=f"CHALLENGE:{req.outcome}",
        level="balanced",
        database="pubmed",
        query=query,
        concepts_used=[req.population, req.intervention, req.outcome, req.comparator],
        generated_by="rules",
    )
    records = (pubmed or PubMedClient()).retrieve(strategy, req.max_results)
    classified = [_classify(req, r) for r in records]

    direct_contrary = [
        r for r in classified
        if r.relevance == "direct" and r.challenge_signal == "potentially_contradictory"
    ]
    higher_level = [
        r for r in direct_contrary if r.evidence_level == "evidence_synthesis"
    ]
    trial_contrary = [
        r for r in direct_contrary if r.evidence_level == "trial"
    ]

    dimensions.append(ChallengeDimension(
        dimension="external_contradictory_evidence",
        triggered=bool(direct_contrary),
        severity=(
            "critical" if len(higher_level) >= 1 and len(direct_contrary) >= 2
            else "material" if direct_contrary
            else "none"
        ),
        rationale=(
            f"{len(direct_contrary)} directly relevant PubMed record(s) contain abstract-level language potentially inconsistent with the current conclusion."
            if direct_contrary
            else "No directly relevant abstract-level contradictory signal was identified in this adversarial search."
        ),
    ))

    dimensions.append(ChallengeDimension(
        dimension="higher_level_counterevidence",
        triggered=bool(higher_level),
        severity="material" if higher_level else "none",
        rationale=(
            f"{len(higher_level)} directly relevant systematic review/meta-analysis record(s) may challenge the current conclusion."
            if higher_level
            else "No directly relevant evidence-synthesis counter-signal was identified."
        ),
    ))

    # Comparator challenge is about transferability, not just contradiction.
    comparator_issue = bool(req.comparator.strip()) and any(
        r.relevance == "partial" for r in classified
    )
    dimensions.append(ChallengeDimension(
        dimension="comparator_trap",
        triggered=comparator_issue,
        severity="minor" if comparator_issue else "none",
        rationale=(
            "Some relevant evidence uses a different or incompletely matched comparator; superiority should not be generalized across comparators."
            if comparator_issue
            else "No clear alternative-comparator challenge was detected in the examined records."
        ),
    ))

    # Timepoint/durability challenge.
    long_term = [
        r for r in classified
        if r.relevance in {"direct", "partial"}
        and re.search(r"\blong[- ]term\b|\bfollow[- ]up\b|\bmaintenance\b", r.title, flags=re.I)
    ]
    dimensions.append(ChallengeDimension(
        dimension="timepoint_and_durability",
        triggered=bool(long_term),
        severity="minor" if long_term else "unresolved",
        rationale=(
            f"{len(long_term)} relevant record(s) explicitly signal longer-term/follow-up evidence that may alter durability claims."
            if long_term
            else "Durability could not be adequately challenged from titles/abstracts in this search."
        ),
    ))

    critical = [d for d in dimensions if d.triggered and d.severity == "critical"]
    material = [d for d in dimensions if d.triggered and d.severity == "material"]
    minor = [d for d in dimensions if d.triggered and d.severity == "minor"]

    if critical or len(material) >= 3:
        verdict = "materially_weakened"
        revised = (
            conclusion.rstrip(".")
            + ". However, the conclusion is materially weakened by contradictory or insufficiently resolved evidence and should not be treated as stable."
        )
    elif material or minor:
        verdict = "survived_with_qualification"
        revised = (
            conclusion.rstrip(".")
            + ". The direction remains plausible within the analysed corpus, but important qualifications are required before generalizing it."
        )
    elif not records and req.studies_in_body <= 1:
        verdict = "unresolved"
        revised = (
            conclusion.rstrip(".")
            + ". The conclusion remains unresolved because the stored evidence base is sparse and the external challenge search returned no usable records."
        )
    else:
        verdict = "survived"
        revised = (
            conclusion.rstrip(".")
            + ". No material challenge was identified by the current internal and PubMed adversarial checks."
        )

    return ConclusionChallengeResponse(
        original_conclusion=conclusion,
        verdict=verdict,
        revised_conclusion=revised,
        dimensions=dimensions,
        external_query=query,
        records_examined=len(records),
        potential_contradictions=len(direct_contrary),
        higher_level_challenges=len(higher_level),
        records=classified,
        interpretation_boundary=(
            "PubMed challenge records are screened from title/abstract signals only. "
            "They are potential counterevidence, not confirmed contradictions. A materially important "
            "record should be imported as full text and appraised before changing the final evidence conclusion."
        ),
    )
