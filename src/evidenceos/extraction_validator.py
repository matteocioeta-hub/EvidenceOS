from __future__ import annotations
from .models import StructuredExtraction


def validate_provenance(extraction: StructuredExtraction) -> list[str]:
    valid = {s.source_span_id for s in extraction.source_spans}
    errors = []

    for field in extraction.population_fields:
        if not field.source_span_ids:
            errors.append(f"{field.extraction_id}: missing source span")
        for sid in field.source_span_ids:
            if sid not in valid:
                errors.append(f"{field.extraction_id}: unknown source span {sid}")

    for result in extraction.outcomes:
        if not result.source_span_ids:
            errors.append(f"{result.result_id}: missing source span")
        for sid in result.source_span_ids:
            if sid not in valid:
                errors.append(f"{result.result_id}: unknown source span {sid}")

    for field in extraction.methodological_fields:
        if not field.source_span_ids:
            errors.append(f"{field.field_name}: missing source span")
        for sid in field.source_span_ids:
            if sid not in valid:
                errors.append(f"{field.field_name}: unknown source span {sid}")

    return errors
