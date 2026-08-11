from __future__ import annotations
import uuid

from .models import StructuredQuestion, GapHypothesis, ConstructCheck, AntiGapQuery


def _quote(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    return f'"{term}"' if " " in term and not term.startswith('"') else term


class AntiGapQueryGenerator:
    """
    Generate searches designed to find evidence that the proposed gap is false.
    """

    @staticmethod
    def generate(
        question: StructuredQuestion,
        gap: GapHypothesis,
        construct_check: ConstructCheck | None = None,
    ) -> list[AntiGapQuery]:
        population = question.population.label
        intervention = question.intervention.label

        constructs = []
        if construct_check and construct_check.candidate_constructs:
            constructs = construct_check.candidate_constructs
        else:
            constructs = [gap.topic]

        # Add gap-type-specific terminology
        gap_terms = {
            "temporal": ["long-term", "follow-up", "maintenance", "sustained"],
            "comparator": ["active comparator", "comparative effectiveness", "versus exercise", "head-to-head"],
            "precision": ["large trial", "multicenter", "multicentre", "meta-analysis"],
            "quantity": ["systematic review", "meta-analysis", "randomized trial", "randomised trial"],
            "quality": ["low risk of bias", "high quality trial", "methodological quality"],
            "implementation": ["implementation", "adherence", "barriers", "facilitators"],
            "experience": ["qualitative", "interview", "experience", "perspective"],
            "replication": ["replication", "independent trial", "multicenter", "multicentre"],
        }
        extra = gap_terms.get(gap.initial_gap_type, [])

        queries = []

        # PubMed: Boolean-oriented
        construct_group = "(" + " OR ".join(_quote(c) for c in constructs + extra) + ")"
        pubmed_query = (
            f"({_quote(population)}) AND ({_quote(intervention)}) AND {construct_group}"
        )
        queries.append(AntiGapQuery(
            query_id=f"AGQ-{uuid.uuid4().hex[:10].upper()}",
            gap_hypothesis_id=gap.gap_hypothesis_id,
            database="pubmed",
            query=pubmed_query,
            target_constructs=constructs + extra,
            rationale="Searches directly for literature that would demonstrate the proposed gap is already addressed."
        ))

        # OpenAlex: concise semantic query
        oa_query = " ".join([population, intervention, gap.topic, *extra[:3]])
        queries.append(AntiGapQuery(
            query_id=f"AGQ-{uuid.uuid4().hex[:10].upper()}",
            gap_hypothesis_id=gap.gap_hypothesis_id,
            database="openalex",
            query=oa_query,
            target_constructs=constructs + extra,
            rationale="Semantic anti-gap search over the same concept space."
        ))

        return queries
