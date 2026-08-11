from __future__ import annotations
import re
from .models import StructuredExtraction, RoB2Answer

def _all_text(extraction: StructuredExtraction) -> list[tuple[str,str]]:
    return [(s.source_span_id, s.text or "") for s in extraction.source_spans]

def _first_match(extraction: StructuredExtraction, patterns: list[str]) -> tuple[str|None, str|None]:
    for sid, text in _all_text(extraction):
        for pattern in patterns:
            if re.search(pattern, text, flags=re.I|re.S):
                return sid, text
    return None, None

class RoB2SignalExtractor:
    @staticmethod
    def extract(extraction: StructuredExtraction) -> dict[str, RoB2Answer]:
        out = {}

        # D1
        sid, txt = _first_match(extraction, [
            r"computer[- ]generated random",
            r"random sequence (?:was )?computer[- ]generated",
            r"computer[- ]generated sequence",
            r"computer[- ]generated procedure",
            r"random number generator",
            r"randomization list",
            r"randomisation list"
        ])
        out["random_sequence_appropriate"] = RoB2Answer(
            question_id="random_sequence_appropriate",
            response="Y" if sid else "NI",
            rationale="Appropriate random-sequence method reported." if sid else "No clear random-sequence method identified.",
            source_span_ids=[sid] if sid else [],
            extraction_confidence=0.90 if sid else 0.60,
        )

        sid2, txt2 = _first_match(extraction, [
            r"allocation conceal",
            r"concealed allocation",
            r"central random",
            r"sealed opaque envelope",
            r"web[- ]based random"
        ])
        out["allocation_concealed"] = RoB2Answer(
            question_id="allocation_concealed",
            response="Y" if sid2 else "NI",
            rationale="Allocation-concealment signal identified." if sid2 else "No clear allocation-concealment information identified.",
            source_span_ids=[sid2] if sid2 else [],
            extraction_confidence=0.88 if sid2 else 0.60,
        )

        sid3, _ = _first_match(extraction, [
            r"baseline imbalance",
            r"significant baseline difference",
            r"groups differed at baseline"
        ])
        out["baseline_imbalance_problem"] = RoB2Answer(
            question_id="baseline_imbalance_problem",
            response="Y" if sid3 else "NI",
            rationale="Potential baseline imbalance explicitly reported." if sid3 else "No explicit baseline-imbalance problem identified.",
            source_span_ids=[sid3] if sid3 else [],
            extraction_confidence=0.80 if sid3 else 0.50,
        )

        # D2
        sid4, _ = _first_match(extraction, [r"participants were blinded", r"participants were masked"])
        out["participants_aware"] = RoB2Answer(
            question_id="participants_aware",
            response="N" if sid4 else "NI",
            rationale="Participants reported as blinded/masked." if sid4 else "Participant awareness not clearly established.",
            source_span_ids=[sid4] if sid4 else [],
            extraction_confidence=0.85 if sid4 else 0.50,
        )
        sid5, _ = _first_match(extraction, [r"therapists were blinded", r"personnel were blinded", r"care providers were blinded"])
        out["personnel_aware"] = RoB2Answer(
            question_id="personnel_aware",
            response="N" if sid5 else "NI",
            rationale="Personnel reported as blinded." if sid5 else "Personnel awareness not clearly established.",
            source_span_ids=[sid5] if sid5 else [],
            extraction_confidence=0.85 if sid5 else 0.50,
        )
        sid6, _ = _first_match(extraction, [r"deviation from (?:the )?protocol", r"protocol deviation", r"non-adherence"])
        out["deviations_due_to_trial_context"] = RoB2Answer(
            question_id="deviations_due_to_trial_context",
            response="PY" if sid6 else "NI",
            rationale="Potential intervention deviation reported." if sid6 else "No clear trial-context deviation information identified.",
            source_span_ids=[sid6] if sid6 else [],
            extraction_confidence=0.75 if sid6 else 0.45,
        )
        out["deviations_likely_affected_outcome"] = RoB2Answer(
            question_id="deviations_likely_affected_outcome",
            response="NI",
            rationale="Requires contextual judgement beyond deterministic extraction.",
            source_span_ids=[],
            extraction_confidence=0.30,
        )
        sid7, _ = _first_match(extraction, [r"intention[- ]to[- ]treat", r"intention to treat", r"modified intention"])
        out["analysis_appropriate"] = RoB2Answer(
            question_id="analysis_appropriate",
            response="Y" if sid7 else "NI",
            rationale="Intention-to-treat analysis reported." if sid7 else "Appropriateness of analysis cannot be established from extracted signals.",
            source_span_ids=[sid7] if sid7 else [],
            extraction_confidence=0.82 if sid7 else 0.45,
        )

        # D3
        sid8, _ = _first_match(extraction, [r"lost to follow[- ]up", r"missing outcome data", r"attrition", r"complete case"])
        out["outcome_data_available"] = RoB2Answer(
            question_id="outcome_data_available",
            response="NI",
            rationale="Missingness terminology found; proportion/completeness requires result-level analysis." if sid8 else "Outcome-data completeness not clearly established.",
            source_span_ids=[sid8] if sid8 else [],
            extraction_confidence=0.55,
        )
        out["evidence_result_not_biased_by_missingness"] = RoB2Answer(
            question_id="evidence_result_not_biased_by_missingness",
            response="NI",
            rationale="Requires result-level judgement about missingness.",
            source_span_ids=[],
            extraction_confidence=0.30,
        )
        out["missingness_related_to_true_value"] = RoB2Answer(
            question_id="missingness_related_to_true_value",
            response="NI",
            rationale="Cannot be inferred safely without additional evidence.",
            source_span_ids=[],
            extraction_confidence=0.25,
        )

        # D4
        sid9, _ = _first_match(extraction, [r"validated questionnaire", r"validated scale", r"validated instrument"])
        out["measurement_method_inappropriate"] = RoB2Answer(
            question_id="measurement_method_inappropriate",
            response="N" if sid9 else "NI",
            rationale="Validated measurement method explicitly reported." if sid9 else "Appropriateness of measurement method not established.",
            source_span_ids=[sid9] if sid9 else [],
            extraction_confidence=0.75 if sid9 else 0.45,
        )
        out["measurement_differs_between_groups"] = RoB2Answer(
            question_id="measurement_differs_between_groups",
            response="NI",
            rationale="No deterministic signal implemented for differential measurement.",
            source_span_ids=[],
            extraction_confidence=0.25,
        )
        sid10, _ = _first_match(extraction, [r"assessor(?:s)? (?:were )?blinded", r"blinded outcome assessor", r"masked outcome assessor"])
        out["outcome_assessor_aware"] = RoB2Answer(
            question_id="outcome_assessor_aware",
            response="N" if sid10 else "NI",
            rationale="Outcome assessor reported as blinded." if sid10 else "Outcome-assessor awareness not established.",
            source_span_ids=[sid10] if sid10 else [],
            extraction_confidence=0.85 if sid10 else 0.45,
        )
        out["awareness_likely_influenced_assessment"] = RoB2Answer(
            question_id="awareness_likely_influenced_assessment",
            response="NI",
            rationale="Requires outcome-specific contextual judgement.",
            source_span_ids=[],
            extraction_confidence=0.25,
        )

        # D5
        sid11, _ = _first_match(extraction, [r"pre[- ]registered", r"preregistered", r"protocol was registered", r"statistical analysis plan"])
        out["analysis_pre_specified"] = RoB2Answer(
            question_id="analysis_pre_specified",
            response="PY" if sid11 else "NI",
            rationale="Prospective analysis/protocol signal identified." if sid11 else "Prespecification cannot be established.",
            source_span_ids=[sid11] if sid11 else [],
            extraction_confidence=0.75 if sid11 else 0.45,
        )
        out["multiple_measurements_possible"] = RoB2Answer(
            question_id="multiple_measurements_possible",
            response="NI",
            rationale="Requires comparison with protocol/registry and outcome definitions.",
            source_span_ids=[],
            extraction_confidence=0.25,
        )
        out["multiple_analyses_possible"] = RoB2Answer(
            question_id="multiple_analyses_possible",
            response="NI",
            rationale="Requires comparison with planned analyses.",
            source_span_ids=[],
            extraction_confidence=0.25,
        )
        return out
