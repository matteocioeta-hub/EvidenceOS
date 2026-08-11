from __future__ import annotations

from .models import StructuredExtraction
from .source_span_builder import split_into_spans
from .extraction_rules import extract_sample_size, extract_randomization, extract_basic_effects, extract_adjusted_b_results


class ExtractionEngine:
    """
    v0.4 default baseline: deterministic extraction from plain text.

    The optional LLMExtractor can later be used as a second pass, but rule-based
    extraction remains useful for benchmarking and numeric safety checks.
    """

    def extract(self, report_id: str, title: str, text: str) -> StructuredExtraction:
        spans = split_into_spans(report_id, text)
        pop_fields = extract_sample_size(report_id, spans)
        methods = extract_randomization(report_id, spans)
        outcomes = extract_basic_effects(report_id, spans) + extract_adjusted_b_results(report_id, spans)

        return StructuredExtraction(
            report_id=report_id,
            population_fields=pop_fields,
            intervention_arms=[],
            comparator_arms=[],
            outcomes=outcomes,
            methodological_fields=methods,
            source_spans=spans,
        )
