from __future__ import annotations

from .models import StructuredQuestion, RetrievalSummary
from .query_generator import QueryGenerator
from .pubmed_client import PubMedClient
from .openalex_client import OpenAlexClient
from .dedup import deduplicate


class RetrievalEngine:
    def __init__(
        self,
        pubmed: PubMedClient | None = None,
        openalex: OpenAlexClient | None = None,
    ):
        self.pubmed = pubmed or PubMedClient()
        self.openalex = openalex or OpenAlexClient()

    def retrieve(
        self,
        question: StructuredQuestion,
        max_results_per_strategy: int = 50,
    ) -> RetrievalSummary:
        strategies = QueryGenerator.generate_all(question)
        records = []

        for strategy in strategies:
            if strategy.database == "pubmed":
                records.extend(
                    self.pubmed.retrieve(strategy, max_results_per_strategy)
                )
            elif strategy.database == "openalex":
                records.extend(
                    self.openalex.retrieve(strategy, max_results_per_strategy)
                )

        unique = deduplicate(records)

        return RetrievalSummary(
            question_id=question.question_id,
            strategies=strategies,
            records_before_deduplication=len(records),
            records_after_deduplication=len(unique),
            records=unique,
        )
