from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from .models import SearchStrategy
from .pubmed_client import PubMedClient


GapType = Literal["quantity", "precision", "consistency", "temporal", "comparator", "replication"]


class GapFalsificationRequest(BaseModel):
    gap_id: str
    gap_type: GapType
    topic: str = Field(min_length=1)
    statement: str = Field(min_length=3)
    population: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    comparator: str = ""
    timepoint: str = ""
    max_results: int = Field(default=15, ge=5, le=25)


class AntiGapRecord(BaseModel):
    record_id: str
    title: str
    year: int | None = None
    journal: str | None = None
    pmid: str | None = None
    doi: str | None = None
    classification: Literal["direct", "partial", "indirect"]
    rationale: str


class GapFalsificationResponse(BaseModel):
    gap_id: str
    gap_type: GapType
    original_statement: str
    anti_gap_query: str
    records_examined: int
    direct_evidence: int
    partial_evidence: int
    verdict: Literal["rejected", "refined", "not_falsified", "unresolved"]
    revised_gap: str | None = None
    interpretation: str
    records: list[AntiGapRecord] = []
    negative_search_caveat: str


STOP = {
    "adult", "adults", "people", "persons", "patients", "patient", "with",
    "the", "and", "for", "from", "into", "study", "studies", "effect",
    "effects", "therapy", "treatment"
}


def _tokens(value: str) -> list[str]:
    return [
        x.lower() for x in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", value)
        if x.lower() not in STOP
    ]


def _concept_group(value: str) -> str:
    tokens = _tokens(value)
    parts = []
    clean = value.strip().strip('"')
    # Whole phrase plus a few informative component tokens improves recall.
    if clean:
        parts.append(f'"{clean}"' if " " in clean else clean)
    for tok in tokens[:4]:
        item = f'"{tok}"'
        if item not in parts:
            parts.append(item)
    return "(" + " OR ".join(parts) + ")" if parts else '("")'


def _gap_terms(gap_type: str) -> list[str]:
    return {
        "quantity": [
            '"systematic review"', '"meta-analysis"', '"randomized trial"',
            '"randomised trial"', '"clinical trial"'
        ],
        "precision": [
            '"meta-analysis"', multicenter, multicentre, '"large trial"',
            '"sample size"', precision
        ],
        "consistency": [
            heterogeneity, inconsistent, inconsistency, '"meta-analysis"',
            subgroup
        ],
        "temporal": [
            '"long-term"', '"long term"', '"follow-up"', followup,
            maintenance, sustained
        ],
        "comparator": [
            '"head-to-head"', '"comparative effectiveness"', versus,
            comparison, comparator
        ],
        "replication": [
            replication, independent, multicenter, multicentre
        ],
    }.get(gap_type, [])


def build_query(req: GapFalsificationRequest) -> str:
    pop = _concept_group(req.population)
    inter = _concept_group(req.intervention)
    topic = _concept_group(req.topic)
    terms = "(" + " OR ".join(_gap_terms(req.gap_type)) + ")"
    return f"{pop} AND {inter} AND {topic} AND {terms}"


def _overlap(text: str, concept: str) -> bool:
    tokens = _tokens(concept)
    if not tokens:
        return False
    low = text.lower()
    hits = sum(tok in low for tok in tokens)
    return hits >= max(1, min(2, len(tokens)))


def _gap_signal(text: str, gap_type: str, publication_types: list[str]) -> bool:
    low = text.lower()
    pubs = " ".join(publication_types).lower()

    patterns = {
        "quantity": [
            "systematic review", "meta-analysis", "meta analysis",
            "randomized controlled trial", "randomised controlled trial",
            "clinical trial"
        ],
        "precision": [
            "meta-analysis", "meta analysis", "multicenter", "multicentre",
            "large trial", "sample size"
        ],
        "consistency": [
            "heterogeneity", "inconsisten", "subgroup", "meta-analysis",
            "meta analysis"
        ],
        "temporal": [
            "long-term", "long term", "follow-up", "followup",
            "maintenance", "sustained"
        ],
        "comparator": [
            "head-to-head", "comparative effectiveness", " versus ",
            " compared with ", " compared to "
        ],
        "replication": [
            "replication", "independent", "multicenter", "multicentre"
        ],
    }
    return any(p in low for p in patterns.get(gap_type, [])) or any(
        p in pubs for p in patterns.get(gap_type, [])
    )


def _classify(req: GapFalsificationRequest, record) -> tuple[str, str]:
    text = f"{record.title or ''}\n{record.abstract or ''}"
    p = _overlap(text, req.population)
    i = _overlap(text, req.intervention)
    o = _overlap(text, req.topic)
    g = _gap_signal(text, req.gap_type, record.publication_types or [])

    if p and i and o and g:
        return "direct", "Matches the population/intervention/topic and contains a gap-specific counter-signal."
    if p and i and (o or g):
        return "partial", "Matches the core population/intervention but only partially addresses the proposed gap."
    return "indirect", "Retrieved by the anti-gap query but does not sufficiently match the gap hypothesis."


def falsify_gap(
    req: GapFalsificationRequest,
    pubmed: PubMedClient | None = None,
) -> GapFalsificationResponse:
    query = build_query(req)
    strategy = SearchStrategy(
        strategy_id=f"ANTI-{uuid.uuid4().hex[:10].upper()}",
        question_id=req.gap_id,
        level="balanced",
        database="pubmed",
        query=query,
        concepts_used=[
            req.population, req.intervention, req.topic, req.gap_type
        ],
        generated_by="rules",
    )

    client = pubmed or PubMedClient()
    records = client.retrieve(strategy, req.max_results)

    classified = []
    for record in records:
        label, rationale = _classify(req, record)
        classified.append(AntiGapRecord(
            record_id=record.record_id,
            title=record.title,
            year=record.year,
            journal=record.journal,
            pmid=record.pmid,
            doi=record.doi,
            classification=label,
            rationale=rationale,
        ))

    direct = [r for r in classified if r.classification == "direct"]
    partial = [r for r in classified if r.classification == "partial"]

    # Conservative logic: one apparently relevant paper is not enough to declare
    # a proposed gap false. Multiple direct counterexamples are required.
    reject_threshold = 3
    if req.gap_type == "precision":
        reject_threshold = 2

    if len(direct) >= reject_threshold:
        verdict = "rejected"
        revised = None
        interpretation = (
            f"The proposed {req.gap_type} gap is not supported by this anti-gap search: "
            f"{len(direct)} direct counterexample(s) were identified."
        )
    elif direct:
        verdict = "refined"
        revised = (
            f"The literature is not absent for {req.topic}; the remaining question is "
            f"whether existing evidence adequately resolves the {req.gap_type} limitation."
        )
        interpretation = (
            f"{len(direct)} direct counterexample(s) were found. The original gap is too broad "
            "and should be narrowed rather than presented as an absence of research."
        )
    elif records:
        verdict = "not_falsified"
        revised = req.statement
        interpretation = (
            "The anti-gap search did not identify a direct counterexample among the examined "
            "records. This increases plausibility of the gap but does not verify absence."
        )
    else:
        verdict = "unresolved"
        revised = req.statement
        interpretation = (
            "No PubMed records were returned by this anti-gap query. A negative search cannot "
            "establish that the literature is absent; broader terminology or databases may be needed."
        )

    return GapFalsificationResponse(
        gap_id=req.gap_id,
        gap_type=req.gap_type,
        original_statement=req.statement,
        anti_gap_query=query,
        records_examined=len(records),
        direct_evidence=len(direct),
        partial_evidence=len(partial),
        verdict=verdict,
        revised_gap=revised,
        interpretation=interpretation,
        records=classified,
        negative_search_caveat=(
            "Failure to retrieve a counterexample is not proof of a research gap. "
            "Search coverage, indexing, terminology and database scope remain sources of uncertainty."
        ),
    )
