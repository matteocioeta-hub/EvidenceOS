from __future__ import annotations

import os
import uuid
from typing import Any

from .models import StructuredQuestion, EvidenceUnit
from .prompts import QUESTION_SYSTEM_PROMPT


class QuestionEngine:
    def __init__(self, client: Any | None = None, model: str | None = None):
        # Lazy import keeps deterministic/unit-test components usable without
        # installing the OpenAI SDK or configuring credentials.
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai package is required only for live question parsing. "
                    "Install project dependencies with pip install -e '.[dev]'."
                ) from exc
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.client = client
        self.model = model or os.environ.get("OPENAI_MODEL")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL must be set explicitly.")

    def parse(self, question_text: str) -> StructuredQuestion:
        qid = f"Q-{uuid.uuid4().hex[:10].upper()}"
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"question_id must be {qid}\n"
                        f"schema_version must be 0.1.0\n"
                        f"Research question:\n{question_text}"
                    ),
                },
            ],
            text_format=StructuredQuestion,
        )
        parsed = response.output_parsed
        if parsed.original_text != question_text:
            parsed.original_text = question_text
        parsed.question_id = qid
        return parsed

    @staticmethod
    def build_evidence_units(question: StructuredQuestion) -> list[EvidenceUnit]:
        if question.question_type != "intervention_effectiveness":
            return []

        comparator = (
            question.comparator.label
            if question.comparator.specified
            else "unspecified comparator"
        )
        time_label = question.time.label if question.time.specified else "any timepoint"

        if question.outcomes:
            outcome_labels = [o.label for o in question.outcomes]
        else:
            outcome_labels = ["unspecified outcome"]

        units: list[EvidenceUnit] = []
        for index, outcome_label in enumerate(outcome_labels, start=1):
            units.append(
                EvidenceUnit(
                    evidence_unit_id=f"EU-{question.question_id}-{index:02d}",
                    question_id=question.question_id,
                    population=question.population.label,
                    intervention=question.intervention.label,
                    comparator=comparator,
                    outcome=outcome_label,
                    time=time_label,
                )
            )
        return units
