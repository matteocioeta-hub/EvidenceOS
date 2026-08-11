from __future__ import annotations
import re

from .models import StructuredQuestion, SearchStrategy


def _quote(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    if " " in term and not (term.startswith('"') and term.endswith('"')):
        return f'"{term}"'
    return term


def _unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out


class QueryGenerator:
    """
    Deterministic v0.2 query generator.

    AI expansion is intentionally deferred. This lets us benchmark retrieval
    separately from LLM synonym generation.
    """

    @staticmethod
    def _population_terms(q: StructuredQuestion) -> list[str]:
        return _unique([q.population.label, *q.population.concepts])

    @staticmethod
    def _intervention_terms(q: StructuredQuestion) -> list[str]:
        return _unique([q.intervention.label, *q.intervention.concepts])

    @staticmethod
    def _outcome_terms(q: StructuredQuestion) -> list[str]:
        return _unique([o.label for o in q.outcomes])

    @classmethod
    def for_pubmed(cls, q: StructuredQuestion) -> list[SearchStrategy]:
        pop = cls._population_terms(q)
        inter = cls._intervention_terms(q)
        outcomes = cls._outcome_terms(q)

        pop_group = "(" + " OR ".join(_quote(x) for x in pop) + ")"
        int_group = "(" + " OR ".join(_quote(x) for x in inter) + ")"
        out_group = "(" + " OR ".join(_quote(x) for x in outcomes) + ")" if outcomes else ""

        sensitivity = f"{pop_group} AND {int_group}"
        balanced = sensitivity + (f" AND {out_group}" if out_group else "")
        precision = balanced + " AND (randomized controlled trial[pt] OR systematic review[pt] OR meta-analysis[pt])"

        return [
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-PUB-SENS",
                question_id=q.question_id,
                level="high_sensitivity",
                database="pubmed",
                query=sensitivity,
                concepts_used=pop + inter,
            ),
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-PUB-BAL",
                question_id=q.question_id,
                level="balanced",
                database="pubmed",
                query=balanced,
                concepts_used=pop + inter + outcomes,
            ),
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-PUB-PREC",
                question_id=q.question_id,
                level="high_precision",
                database="pubmed",
                query=precision,
                concepts_used=pop + inter + outcomes,
            ),
        ]

    @classmethod
    def for_openalex(cls, q: StructuredQuestion) -> list[SearchStrategy]:
        pop = cls._population_terms(q)
        inter = cls._intervention_terms(q)
        outcomes = cls._outcome_terms(q)

        # OpenAlex works search is free-text; avoid PubMed field tags.
        sensitivity = " ".join([pop[0] if pop else "", inter[0] if inter else ""]).strip()
        balanced = " ".join(
            [pop[0] if pop else "", inter[0] if inter else "", *(outcomes[:2])]
        ).strip()
        precision = balanced + " randomized trial systematic review"

        return [
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-OA-SENS",
                question_id=q.question_id,
                level="high_sensitivity",
                database="openalex",
                query=sensitivity,
                concepts_used=pop + inter,
            ),
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-OA-BAL",
                question_id=q.question_id,
                level="balanced",
                database="openalex",
                query=balanced,
                concepts_used=pop + inter + outcomes,
            ),
            SearchStrategy(
                strategy_id=f"S-{q.question_id}-OA-PREC",
                question_id=q.question_id,
                level="high_precision",
                database="openalex",
                query=precision,
                concepts_used=pop + inter + outcomes,
            ),
        ]

    @classmethod
    def generate_all(cls, q: StructuredQuestion) -> list[SearchStrategy]:
        if q.question_type != "intervention_effectiveness":
            return []
        return cls.for_pubmed(q) + cls.for_openalex(q)
