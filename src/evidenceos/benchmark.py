from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import CanonicalRecord
from .dedup import normalize_title


def _record_matches(record: CanonicalRecord, identifier_type: str, identifier: str) -> bool:
    if identifier_type == "pmid":
        return bool(record.pmid and record.pmid.strip() == identifier.strip())
    if identifier_type == "doi":
        from .dedup import normalize_doi
        return normalize_doi(record.doi) == normalize_doi(identifier)
    if identifier_type == "title_contains":
        return normalize_title(identifier) in normalize_title(record.title)
    raise ValueError(f"Unsupported identifier_type: {identifier_type}")


def evaluate_key_evidence_recall(
    records: Iterable[CanonicalRecord],
    gold_path: str | Path,
    case_id: str,
) -> dict:
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    case = next(c for c in gold["cases"] if c["case_id"] == case_id)
    records = list(records)

    rows = []
    for item in case["required_key_evidence"]:
        found = any(
            _record_matches(r, item["identifier_type"], item["identifier"])
            for r in records
        )
        rows.append({**item, "found": found})

    required = [r for r in rows if r.get("must_retrieve")]
    found_required = sum(1 for r in required if r["found"])
    recall = found_required / len(required) if required else 1.0

    return {
        "case_id": case_id,
        "required_items": len(required),
        "required_items_found": found_required,
        "key_evidence_recall": recall,
        "details": rows,
    }
