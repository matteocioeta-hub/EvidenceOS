from __future__ import annotations
import re
import uuid

from .models import SourceSpan


SECTION_HEADINGS = [
    "abstract", "introduction", "methods", "method", "participants",
    "interventions", "randomization", "randomisation", "results",
    "discussion", "conclusion", "conclusions"
]


def split_into_spans(report_id: str, text: str, max_chars: int = 1800) -> list[SourceSpan]:
    """
    Lightweight provenance segmentation for plain-text reports.

    It does not attempt PDF layout reconstruction. It creates auditable,
    stable source chunks that downstream extractors can cite.
    """
    if not text:
        return []

    spans = []
    cursor = 0
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    current_section = None

    for idx, para in enumerate(paragraphs, start=1):
        low = para.strip().lower().rstrip(":")
        if len(para) < 120 and any(low == h for h in SECTION_HEADINGS):
            current_section = low
            cursor += len(para) + 2
            continue

        start = text.find(para, cursor)
        if start < 0:
            start = cursor
        end = start + len(para)

        # split oversized paragraphs
        if len(para) > max_chars:
            local = 0
            while local < len(para):
                chunk = para[local:local+max_chars]
                spans.append(
                    SourceSpan(
                        source_span_id=f"SPAN-{uuid.uuid4().hex[:10].upper()}",
                        report_id=report_id,
                        section=current_section,
                        paragraph=idx,
                        text=chunk,
                        char_start=start+local,
                        char_end=start+local+len(chunk),
                    )
                )
                local += max_chars
        else:
            spans.append(
                SourceSpan(
                    source_span_id=f"SPAN-{uuid.uuid4().hex[:10].upper()}",
                    report_id=report_id,
                    section=current_section,
                    paragraph=idx,
                    text=para,
                    char_start=start,
                    char_end=end,
                )
            )
        cursor = end

    return spans
