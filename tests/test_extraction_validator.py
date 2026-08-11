from evidenceos.models import StructuredExtraction, SourceSpan, ExtractionField
from evidenceos.extraction_validator import validate_provenance


def test_valid_provenance():
    span = SourceSpan(
        source_span_id="S1",
        report_id="R1",
        text="The sample size was 100."
    )
    field = ExtractionField(
        extraction_id="E1",
        report_id="R1",
        field_name="sample_size",
        value=100,
        source_span_ids=["S1"],
        extraction_method="rules",
        extraction_confidence=0.9,
    )
    ex = StructuredExtraction(
        report_id="R1",
        population_fields=[field],
        source_spans=[span],
    )
    assert validate_provenance(ex) == []


def test_invalid_provenance_detected():
    span = SourceSpan(
        source_span_id="S1",
        report_id="R1",
        text="The sample size was 100."
    )
    field = ExtractionField(
        extraction_id="E1",
        report_id="R1",
        field_name="sample_size",
        value=100,
        source_span_ids=["UNKNOWN"],
        extraction_method="rules",
        extraction_confidence=0.9,
    )
    ex = StructuredExtraction(
        report_id="R1",
        population_fields=[field],
        source_spans=[span],
    )
    errors = validate_provenance(ex)
    assert len(errors) == 1
