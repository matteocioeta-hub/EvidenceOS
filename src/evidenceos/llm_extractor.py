from __future__ import annotations
import os

from .models import StructuredExtraction, SourceSpan
from .extraction_prompts import EXTRACTION_SYSTEM_PROMPT


class LLMExtractor:
    def __init__(self, model: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "LLM extraction requires the optional dependency: pip install -e '.[llm]'"
            ) from exc

        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get("OPENAI_MODEL")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL must be set explicitly.")

    def extract(
        self,
        report_id: str,
        title: str,
        spans: list[SourceSpan],
    ) -> StructuredExtraction:
        payload = {
            "report_id": report_id,
            "title": title,
            "source_spans": [s.model_dump() for s in spans],
        }

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": str(payload)},
            ],
            text_format=StructuredExtraction,
        )
        extraction = response.output_parsed

        # hard provenance guardrail
        valid_ids = {s.source_span_id for s in spans}
        referenced = set()
        for field in extraction.population_fields:
            referenced.update(field.source_span_ids)
        for result in extraction.outcomes:
            referenced.update(result.source_span_ids)
        for field in extraction.methodological_fields:
            referenced.update(field.source_span_ids)

        unknown = referenced - valid_ids
        if unknown:
            raise ValueError(f"Extraction referenced unknown source spans: {sorted(unknown)}")

        extraction.report_id = report_id
        extraction.source_spans = spans
        return extraction
