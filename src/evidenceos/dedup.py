from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .models import CanonicalRecord


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.lower().replace("https://doi.org/", "").replace("doi:", "").strip()


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _merge(a: CanonicalRecord, b: CanonicalRecord) -> CanonicalRecord:
    data = a.model_dump()
    other = b.model_dump()

    for field in ["abstract", "year", "journal", "doi", "pmid", "openalex_id",
                  "is_open_access", "cited_by_count"]:
        if data.get(field) in (None, "", []):
            data[field] = other.get(field)

    data["authors"] = list(dict.fromkeys([*a.authors, *b.authors]))
    data["source_databases"] = list(
        dict.fromkeys([*a.source_databases, *b.source_databases])
    )
    data["publication_types"] = list(
        dict.fromkeys([*a.publication_types, *b.publication_types])
    )

    # Prefer PMID as stable biomedical record identifier when available.
    if data.get("pmid"):
        data["record_id"] = f"PMID:{data['pmid']}"
    elif data.get("doi"):
        data["record_id"] = f"DOI:{normalize_doi(data['doi'])}"

    return CanonicalRecord(**data)


def same_record(a: CanonicalRecord, b: CanonicalRecord) -> bool:
    da, db = normalize_doi(a.doi), normalize_doi(b.doi)
    if da and db and da == db:
        return True
    if a.pmid and b.pmid and a.pmid == b.pmid:
        return True

    ta, tb = normalize_title(a.title), normalize_title(b.title)
    if not ta or not tb:
        return False
    similarity = SequenceMatcher(None, ta, tb).ratio()
    same_year = (a.year is None or b.year is None or a.year == b.year)
    return similarity >= 0.96 and same_year


def deduplicate(records: list[CanonicalRecord]) -> list[CanonicalRecord]:
    out: list[CanonicalRecord] = []
    for record in records:
        for i, existing in enumerate(out):
            if same_record(existing, record):
                out[i] = _merge(existing, record)
                break
        else:
            out.append(record)
    return out
