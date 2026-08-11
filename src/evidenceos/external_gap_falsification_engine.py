from __future__ import annotations

from .models import ExternalGapFalsificationResult
from .anti_gap_query_generator import AntiGapQueryGenerator
from .external_gap_classifier import ExternalGapEvidenceClassifier
from .pubmed_client import PubMedClient
from .openalex_client import OpenAlexClient
from .models import SearchStrategy


class ExternalGapFalsificationEngine:
    def __init__(self, pubmed=None, openalex=None):
        self.pubmed = pubmed or PubMedClient()
        self.openalex = openalex or OpenAlexClient()

    def run(self, question, gap_hypothesis, construct_check=None, max_results_per_query=25):
        queries = AntiGapQueryGenerator.generate(question, gap_hypothesis, construct_check)
        records = []

        for q in queries:
            strategy = SearchStrategy(
                strategy_id=q.query_id,
                question_id=question.question_id,
                level="high_sensitivity",
                database=q.database,
                query=q.query,
                concepts_used=q.target_constructs,
                generated_by="rules",
            )
            if q.database == "pubmed":
                records.extend(self.pubmed.retrieve(strategy, max_results_per_query))
            elif q.database == "openalex":
                records.extend(self.openalex.retrieve(strategy, max_results_per_query))

        # Deduplicate using existing utility
        from .dedup import deduplicate
        records = deduplicate(records)

        evidence = [
            ExternalGapEvidenceClassifier.classify(
                question, gap_hypothesis, construct_check, r
            )
            for r in records
        ]

        direct_against = [e for e in evidence if e.relation_to_gap=="against_gap" and e.directness=="direct"]
        partial_against = [e for e in evidence if e.relation_to_gap=="against_gap" and e.directness=="partial"]

        if len(direct_against) >= 2:
            verdict = "reject"
            rationale = "Multiple direct records were identified that address the proposed gap."
            confidence = "high"
        elif len(direct_against) == 1 or len(partial_against) >= 2:
            verdict = "refine"
            rationale = "Related evidence exists; the original gap statement should be narrowed rather than accepted as a simple absence of evidence."
            confidence = "moderate"
        elif len(evidence) == 0:
            verdict = "strengthen"
            rationale = "No records were retrieved by the dedicated anti-gap searches. This strengthens, but does not prove, the gap hypothesis."
            confidence = "moderate"
        else:
            verdict = "unresolved"
            rationale = "Retrieved records were insufficiently direct to confirm or falsify the gap."
            confidence = "low"

        return ExternalGapFalsificationResult(
            gap_hypothesis_id=gap_hypothesis.gap_hypothesis_id,
            anti_gap_queries=queries,
            external_evidence=evidence,
            external_verdict=verdict,
            rationale=rationale,
            confidence=confidence,
        )
