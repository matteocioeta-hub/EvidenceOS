from __future__ import annotations
import uuid
from .models import StructuredExtraction, RoB2Assessment, RoB2DomainAssessment
from .rob2_signal_extractor import RoB2SignalExtractor
from .rob2_outcome_context import apply_outcome_context
from . import rob2_rules

DOMAIN_INFO = {
    "D1": ("Bias arising from the randomization process",
           ["random_sequence_appropriate","allocation_concealed","baseline_imbalance_problem"]),
    "D2": ("Bias due to deviations from intended interventions",
           ["participants_aware","personnel_aware","deviations_due_to_trial_context",
            "deviations_likely_affected_outcome","analysis_appropriate"]),
    "D3": ("Bias due to missing outcome data",
           ["outcome_data_available","evidence_result_not_biased_by_missingness",
            "missingness_related_to_true_value"]),
    "D4": ("Bias in measurement of the outcome",
           ["measurement_method_inappropriate","measurement_differs_between_groups",
            "outcome_assessor_aware","awareness_likely_influenced_assessment"]),
    "D5": ("Bias in selection of the reported result",
           ["analysis_pre_specified","multiple_measurements_possible","multiple_analyses_possible"]),
}

JUDGES = {
    "D1": rob2_rules.judge_d1,
    "D2": rob2_rules.judge_d2,
    "D3": rob2_rules.judge_d3,
    "D4": rob2_rules.judge_d4,
    "D5": rob2_rules.judge_d5,
}

class RoB2Engine:
    def assess(self, extraction: StructuredExtraction, result_id: str|None=None, effect_of_interest: str="assignment") -> RoB2Assessment:
        signals = RoB2SignalExtractor.extract(extraction)
        signals = apply_outcome_context(extraction, result_id, signals)
        domains = []
        all_source_ids = set()

        for did, (name, keys) in DOMAIN_INFO.items():
            judgement, rationale = JUDGES[did](signals)
            answers = [signals[k] for k in keys]
            source_ids = []
            for a in answers:
                source_ids.extend(a.source_span_ids)
            source_ids = list(dict.fromkeys(source_ids))
            all_source_ids.update(source_ids)
            domains.append(RoB2DomainAssessment(
                domain_id=did,
                domain_name=name,
                signalling_answers=answers,
                judgement=judgement,
                rationale=rationale,
                source_span_ids=source_ids,
                judgement_method="rules",
            ))

        overall_judgement, overall_rationale = rob2_rules.overall(domains)
        return RoB2Assessment(
            assessment_id=f"ROB2-{uuid.uuid4().hex[:10].upper()}",
            report_id=extraction.report_id,
            result_id=result_id,
            effect_of_interest=effect_of_interest,
            domains=domains,
            overall_judgement=overall_judgement,
            overall_rationale=overall_rationale,
            source_span_ids=sorted(all_source_ids),
        )
