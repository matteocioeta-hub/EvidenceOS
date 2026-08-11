from __future__ import annotations

from .models import StructuredQuestion, RetrievalSummary
from .query_generator import QueryGenerator
from .pubmed_client import PubMedClient
from .dedup import deduplicate


class RetrievalEngine:
    """
    PubMed-only retrieval engine for the public alpha.

    OpenAlex is intentionally disabled in this release to reduce external
    dependencies and make the live retrieval path easier to validate.

    The rest of the EvidenceOS pipeline remains unchanged:
    question -> query generation -> PubMed -> deduplication -> study intelligence.
    """

    def __init__(self, pubmed: PubMedClient | None = None):
        self.pubmed = pubmed or PubMedClient()

    def retrieve(
        self,
        question: StructuredQuestion,
        max_results_per_strategy: int = 50,
    ) -> RetrievalSummary:
        all_strategies = QueryGenerator.generate_all(question)

        # Keep only PubMed strategies.
        strategies = [
            strategy
            for strategy in all_strategies
            if strategy.database == "pubmed"
        ]

        records = []
        for strategy in strategies:
            records.extend(
                self.pubmed.retrieve(
                    strategy,
                    max_results_per_strategy,
                )
            )

        unique = deduplicate(records)

        return RetrievalSummary(
            question_id=question.question_id,
            strategies=strategies,
            records_before_deduplication=len(records),
            records_after_deduplication=len(unique),
            records=unique,
        )
