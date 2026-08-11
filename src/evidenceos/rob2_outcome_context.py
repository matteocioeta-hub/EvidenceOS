from __future__ import annotations
from .models import StructuredExtraction

PATIENT_REPORTED = {"VAS 0-100", "RMDQ 0-24", "NPRS", "VAS"}

def apply_outcome_context(extraction, result_id, signals):
    if not result_id:
        return signals

    result = next((r for r in extraction.outcomes if r.result_id == result_id), None)
    if not result:
        return signals

    if result.instrument in PATIENT_REPORTED:
        # In a patient-reported outcome, the participant is effectively the outcome assessor.
        # If no participant blinding is reported for visibly different exercise interventions,
        # awareness is treated as probable rather than "no information".
        pa = signals["participants_aware"]
        if pa.response == "NI":
            pa.response = "PY"
            pa.rationale = (
                "Outcome is patient-reported and the interventions are visibly different; "
                "participant awareness of assignment is probable."
            )
            pa.extraction_confidence = 0.80

        oa = signals["outcome_assessor_aware"]
        if oa.response == "NI":
            oa.response = "PY"
            oa.rationale = (
                "For patient-reported outcomes the participant is the assessor; "
                "awareness of assignment is probable."
            )
            oa.extraction_confidence = 0.85

        infl = signals["awareness_likely_influenced_assessment"]
        if infl.response == "NI":
            infl.response = "PY"
            infl.rationale = (
                "Knowledge of receiving high-load versus low-load exercise could plausibly influence "
                "self-reported pain/disability ratings."
            )
            infl.extraction_confidence = 0.70

    return signals
