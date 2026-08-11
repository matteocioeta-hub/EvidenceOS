from __future__ import annotations
import uuid
from pydantic import BaseModel, Field

from .models import StructuredQuestion, Concept, Comparator, Outcome, TimeSpec, Ambiguity
from .retrieval_engine import RetrievalEngine
from .study_intelligence_engine import StudyIntelligenceEngine


class GuidedSearchRequest(BaseModel):
    question: str = Field(min_length=3)
    population: str = Field(min_length=2)
    intervention: str = Field(min_length=2)
    comparator: str = ""
    outcomes: list[str] = Field(min_length=1)
    timepoint: str = ""
    max_results_per_strategy: int = Field(default=20, ge=5, le=50)


class GuidedSearchResponse(BaseModel):
    structured_question: StructuredQuestion
    retrieval: dict
    study_intelligence: dict


def build_guided_question(request: GuidedSearchRequest) -> StructuredQuestion:
    qid = f"Q-{uuid.uuid4().hex[:10].upper()}"
    outcomes = [
        Outcome(outcome_id=f"OUT-{i:02d}", label=o.strip())
        for i, o in enumerate(request.outcomes, start=1)
        if o.strip()
    ]
    comp = request.comparator.strip()
    tp = request.timepoint.strip()

    ambiguities = []
    if not comp:
        ambiguities.append(
            Ambiguity(
                field="comparator",
                message="Comparator not specified; retrieval will remain broad.",
                severity="info",
            )
        )
    if not tp:
        ambiguities.append(
            Ambiguity(
                field="time",
                message="Timepoint not specified; all timepoints are eligible.",
                severity="info",
            )
        )

    return StructuredQuestion(
        question_id=qid,
        original_text=request.question,
        normalized_text=request.question.strip(),
        question_type="intervention_effectiveness",
        framework="PICO",
        question_status="well_specified" if comp and tp else "partially_specified",
        population=Concept(
            label=request.population.strip(),
            specified=True,
            concepts=[request.population.strip()],
        ),
        intervention=Concept(
            label=request.intervention.strip(),
            specified=True,
            concepts=[request.intervention.strip()],
        ),
        comparator=Comparator(
            label=comp or "unspecified comparator",
            specified=bool(comp),
            types=[],
        ),
        outcomes=outcomes,
        time=TimeSpec(
            specified=bool(tp),
            label=tp or "any timepoint",
        ),
        ambiguities=ambiguities,
        model_confidence=1.0,
    )


def run_guided_search(request: GuidedSearchRequest) -> GuidedSearchResponse:
    question = build_guided_question(request)
    retrieval = RetrievalEngine().retrieve(
        question,
        max_results_per_strategy=request.max_results_per_strategy,
    )
    intelligence = StudyIntelligenceEngine().analyse(question, retrieval.records)

    return GuidedSearchResponse(
        structured_question=question,
        retrieval=retrieval.model_dump(),
        study_intelligence=intelligence.model_dump(),
    )
