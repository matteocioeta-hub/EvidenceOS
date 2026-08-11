from __future__ import annotations

from .models import StructuredQuestion, RetrievalSummary
from .query_generator import QueryGenerator
from .pubmed_client import PubMedClient
from .dedup import deduplicate


class RetrievalEngine:
    """
    Stable PubMed-only retrieval for the public alpha.

    To reduce latency and NCBI rate-limit pressure in a synchronous web request,
    the live public endpoint executes one balanced PubMed strategy rather than
    three overlapping strategies. Query generation still exposes the full
    strategy family for future asynchronous/deep-search workflows.
    """

    def __init__(self, pubmed: PubMedClient | None = None):
        self.pubmed = pubmed or PubMedClient()

    def retrieve(
        self,
        question: StructuredQuestion,
        max_results_per_strategy: int = 50,
    ) -> RetrievalSummary:
        pubmed_strategies = QueryGenerator.for_pubmed(question)

        # Prefer the balanced strategy for the synchronous public web app.
        balanced = next(
            (s for s in pubmed_strategies if s.level == "balanced"),
            pubmed_strategies[0] if pubmed_strategies else None,
        )

        if balanced is None:
            return RetrievalSummary(
                question_id=question.question_id,
                strategies=[],
                records_before_deduplication=0,
                records_after_deduplication=0,
                records=[],
            )

        records = self.pubmed.retrieve(
            balanced,
            max_results_per_strategy,
        )
        unique = deduplicate(records)

        return RetrievalSummary(
            question_id=question.question_id,
            strategies=[balanced],
            records_before_deduplication=len(records),
            records_after_deduplication=len(unique),
            records=unique,
        )
