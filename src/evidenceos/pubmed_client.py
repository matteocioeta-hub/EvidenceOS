from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Iterable

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
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=30.0)
        self.tool = os.environ.get("NCBI_TOOL", "EvidenceOS")
        self.email = os.environ.get("NCBI_EMAIL")
        self.api_key = os.environ.get("NCBI_API_KEY")

    def _common(self) -> dict:
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search_ids(self, strategy: SearchStrategy, max_results: int) -> list[str]:
        params = {
            **self._common(),
            "db": "pubmed",
            "term": strategy.query,
            "retmode": "json",
            "retmax": max_results,
        }
        r = self.client.get(f"{BASE}/esearch.fcgi", params=params)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])

    def fetch(self, pmids: list[str]) -> list[CanonicalRecord]:
        if not pmids:
            return []
        params = {
            **self._common(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        r = self.client.get(f"{BASE}/efetch.fcgi", params=params)
        r.raise_for_status()
        root = ET.fromstring(r.text)
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
                import re
                m = re.search(r"(19|20)\d{2}", year_text)
                if m:
                    year = int(m.group(0))

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
                _text(x) for x in article.findall("./PublicationTypeList/PublicationType")
            ]
            publication_types = [x for x in publication_types if x]

            doi = _doi_from_article(item)

            records.append(
                CanonicalRecord(
                    record_id=f"PMID:{pmid}" if pmid else f"PUBMED:{len(records)+1}",
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

    def retrieve(self, strategy: SearchStrategy, max_results: int) -> list[CanonicalRecord]:
        return self.fetch(self.search_ids(strategy, max_results))
