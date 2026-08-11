from __future__ import annotations

import os
import httpx

from .models import CanonicalRecord, SearchStrategy


BASE = "https://api.openalex.org/works"


def _abstract_from_inverted(index: dict | None) -> str | None:
    if not index:
        return None
    positions = []
    for word, locs in index.items():
        for loc in locs:
            positions.append((loc, word))
    positions.sort()
    return " ".join(word for _, word in positions) or None


class OpenAlexClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=30.0)
        self.api_key = os.environ.get("OPENALEX_API_KEY")

    def retrieve(self, strategy: SearchStrategy, max_results: int) -> list[CanonicalRecord]:
        if not self.api_key:
            raise RuntimeError("OPENALEX_API_KEY is required for OpenAlex retrieval.")

        params = {
            "search": strategy.query,
            "per-page": min(max_results, 100),
            "api_key": self.api_key,
        }
        r = self.client.get(BASE, params=params)
        r.raise_for_status()
        data = r.json()

        records: list[CanonicalRecord] = []
        for work in data.get("results", []):
            ids = work.get("ids") or {}
            doi = ids.get("doi") or work.get("doi")
            if doi:
                doi = doi.lower().replace("https://doi.org/", "").strip()

            pmid = ids.get("pmid")
            if pmid:
                pmid = pmid.replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip("/")

            authors = []
            for authorship in work.get("authorships") or []:
                name = (authorship.get("author") or {}).get("display_name")
                if name:
                    authors.append(name)

            source = (((work.get("primary_location") or {}).get("source")) or {})
            journal = source.get("display_name")

            open_access = work.get("open_access") or {}

            records.append(
                CanonicalRecord(
                    record_id=work.get("id") or f"OPENALEX:{len(records)+1}",
                    title=work.get("display_name") or work.get("title") or "[Untitled]",
                    abstract=_abstract_from_inverted(work.get("abstract_inverted_index")),
                    year=work.get("publication_year"),
                    journal=journal,
                    authors=authors,
                    doi=doi,
                    pmid=pmid,
                    openalex_id=work.get("id"),
                    source_databases=["openalex"],
                    publication_types=[work.get("type")] if work.get("type") else [],
                    is_open_access=open_access.get("is_oa"),
                    cited_by_count=work.get("cited_by_count"),
                )
            )
        return records
