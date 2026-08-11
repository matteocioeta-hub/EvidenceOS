from __future__ import annotations

import os
import random
import re
import threading
import time
import xml.etree.ElementTree as ET

import httpx

from .models import CanonicalRecord, SearchStrategy


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _text(node) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _doi_from_article(article) -> str | None:
    for eloc in article.findall(".//ELocationID"):
        if eloc.attrib.get("EIdType") == "doi":
            val = _text(eloc)
            if val:
                return val.lower()
    for aid in article.findall(".//ArticleId"):
        if aid.attrib.get("IdType") == "doi":
            val = _text(aid)
            if val:
                return val.lower()
    return None


class PubMedClient:
    """
    NCBI E-utilities client with:
    - request pacing;
    - retry/backoff for 429 and transient 5xx errors;
    - Retry-After support;
    - optional NCBI_API_KEY;
    - optional NCBI_EMAIL / NCBI_TOOL metadata.

    Environment variables:
      NCBI_TOOL
      NCBI_EMAIL
      NCBI_API_KEY
      NCBI_MAX_RETRIES
      NCBI_REQUEST_INTERVAL
    """

    _lock = threading.Lock()
    _last_request_at = 0.0

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            headers={"User-Agent": "EvidenceOS/0.1"},
        )
        self.tool = os.environ.get("NCBI_TOOL", "EvidenceOS")
        self.email = os.environ.get("NCBI_EMAIL")
        self.api_key = os.environ.get("NCBI_API_KEY")

        self.max_retries = int(os.environ.get("NCBI_MAX_RETRIES", "5"))

        # Conservative defaults:
        # ~2.5 req/s without API key, ~8 req/s with API key.
        default_interval = "0.125" if self.api_key else "0.40"
        self.request_interval = float(
            os.environ.get("NCBI_REQUEST_INTERVAL", default_interval)
        )

    def _common(self) -> dict:
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _pace(self) -> None:
        """
        Process-local rate limiter.

        This intentionally stays below NCBI's usual ceilings because cloud
        deployments may share an outbound IP with unrelated workloads.
        """
        with self._lock:
            now = time.monotonic()
            wait = self.request_interval - (now - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self.__class__._last_request_at = time.monotonic()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    def _get(self, url: str, *, params: dict) -> httpx.Response:
        """
        GET with exponential backoff for rate limiting and transient server errors.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._pace()

            try:
                response = self.client.get(url, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise

                delay = min(20.0, (2 ** attempt) * 0.8) + random.uniform(0.0, 0.35)
                time.sleep(delay)
                continue

            if response.status_code < 400:
                return response

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt >= self.max_retries:
                    response.raise_for_status()

                retry_after = self._retry_after_seconds(response)
                delay = (
                    retry_after
                    if retry_after is not None
                    else min(30.0, (2 ** attempt) * 1.2)
                    + random.uniform(0.0, 0.5)
                )
                time.sleep(delay)
                continue

            response.raise_for_status()

        if last_error is not None:
            raise last_error
        raise RuntimeError("NCBI request failed after retries.")

    def search_ids(self, strategy: SearchStrategy, max_results: int) -> list[str]:
        params = {
            **self._common(),
            "db": "pubmed",
            "term": strategy.query,
            "retmode": "json",
            "retmax": max_results,
        }
        response = self._get(f"{BASE}/esearch.fcgi", params=params)
        payload = response.json()
        return payload.get("esearchresult", {}).get("idlist", [])

    def fetch(self, pmids: list[str]) -> list[CanonicalRecord]:
        if not pmids:
            return []

        params = {
            **self._common(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        response = self._get(f"{BASE}/efetch.fcgi", params=params)
        root = ET.fromstring(response.text)
        records: list[CanonicalRecord] = []

        for item in root.findall(".//PubmedArticle"):
            citation = item.find("./MedlineCitation")
            article = item.find("./MedlineCitation/Article")
            if citation is None or article is None:
                continue

            pmid = _text(citation.find("./PMID"))
            title = _text(article.find("./ArticleTitle")) or "[Untitled]"

            abstract_parts = [
                _text(x) for x in article.findall("./Abstract/AbstractText")
            ]
            abstract = " ".join(x for x in abstract_parts if x) or None

            journal = _text(article.find("./Journal/Title"))

            year = None
            year_text = (
                _text(article.find("./Journal/JournalIssue/PubDate/Year"))
                or _text(article.find("./Journal/JournalIssue/PubDate/MedlineDate"))
            )
            if year_text:
                match = re.search(r"(19|20)\d{2}", year_text)
                if match:
                    year = int(match.group(0))

            authors = []
            for author in article.findall("./AuthorList/Author"):
                collective = _text(author.find("./CollectiveName"))
                if collective:
                    authors.append(collective)
                    continue

                fore = _text(author.find("./ForeName")) or ""
                last = _text(author.find("./LastName")) or ""
                name = f"{fore} {last}".strip()
                if name:
                    authors.append(name)

            publication_types = [
                _text(x)
                for x in article.findall(
                    "./PublicationTypeList/PublicationType"
                )
            ]
            publication_types = [x for x in publication_types if x]

            doi = _doi_from_article(item)

            records.append(
                CanonicalRecord(
                    record_id=f"PMID:{pmid}"
                    if pmid
                    else f"PUBMED:{len(records) + 1}",
                    title=title,
                    abstract=abstract,
                    year=year,
                    journal=journal,
                    authors=authors,
                    doi=doi,
                    pmid=pmid,
                    source_databases=["pubmed"],
                    publication_types=publication_types,
                )
            )

        return records

    def retrieve(
        self,
        strategy: SearchStrategy,
        max_results: int,
    ) -> list[CanonicalRecord]:
        pmids = self.search_ids(strategy, max_results)
        return self.fetch(pmids)
