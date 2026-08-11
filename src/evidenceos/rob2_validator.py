from __future__ import annotations
from .models import StructuredExtraction, RoB2Assessment

def validate_rob2_provenance(extraction: StructuredExtraction, assessment: RoB2Assessment) -> list[str]:
    valid = {s.source_span_id for s in extraction.source_spans}
    errors = []
    for domain in assessment.domains:
        for sid in domain.source_span_ids:
            if sid not in valid:
                errors.append(f"{domain.domain_id}: unknown source span {sid}")
        for answer in domain.signalling_answers:
            for sid in answer.source_span_ids:
                if sid not in valid:
                    errors.append(f"{answer.question_id}: unknown source span {sid}")
    for sid in assessment.source_span_ids:
        if sid not in valid:
            errors.append(f"overall: unknown source span {sid}")
    return errors
