from __future__ import annotations
from .models import RoB2Answer

def _r(signals, key):
    return signals[key].response

def judge_d1(signals):
    seq = _r(signals,"random_sequence_appropriate")
    conceal = _r(signals,"allocation_concealed")
    imbalance = _r(signals,"baseline_imbalance_problem")
    if imbalance in {"Y","PY"}:
        return "some_concerns", "Potential baseline imbalance creates concern about the randomization process."
    if seq in {"Y","PY"} and conceal in {"Y","PY"}:
        return "low", "Random sequence and allocation concealment were both supported; no explicit baseline-imbalance concern was identified."
    if seq == "NI" or conceal == "NI":
        return "some_concerns", "Key randomization information is insufficiently reported."
    return "unresolved", "Randomization process could not be determined."

def judge_d2(signals):
    analysis = _r(signals,"analysis_appropriate")
    dev = _r(signals,"deviations_due_to_trial_context")
    affected = _r(signals,"deviations_likely_affected_outcome")
    if dev in {"Y","PY"} and affected in {"Y","PY"}:
        return "high", "Deviations from intended intervention likely affected the outcome."
    if analysis in {"Y","PY"} and dev in {"N","PN","NI"}:
        return "low" if dev in {"N","PN"} else "some_concerns", (
            "Analysis appears appropriate; deviation information is incomplete." if dev=="NI"
            else "No important deviations identified and analysis appears appropriate."
        )
    return "some_concerns", "Insufficient information about deviations and/or analysis."

def judge_d3(signals):
    avail = _r(signals,"outcome_data_available")
    unbiased = _r(signals,"evidence_result_not_biased_by_missingness")
    related = _r(signals,"missingness_related_to_true_value")
    if avail in {"Y","PY"}:
        return "low", "Outcome data were sufficiently available."
    if unbiased in {"Y","PY"}:
        return "low", "Evidence suggests missingness did not bias the result."
    if related in {"Y","PY"}:
        return "high", "Missingness may depend on the true outcome value."
    return "some_concerns", "Missing-outcome-data risk cannot be ruled out."

def judge_d4(signals):
    inappropriate = _r(signals,"measurement_method_inappropriate")
    differs = _r(signals,"measurement_differs_between_groups")
    aware = _r(signals,"outcome_assessor_aware")
    influenced = _r(signals,"awareness_likely_influenced_assessment")
    if inappropriate in {"Y","PY"} or differs in {"Y","PY"}:
        return "high", "Outcome measurement may be inappropriate or differ between groups."
    if aware in {"Y","PY"} and influenced in {"Y","PY"}:
        return "high", "Assessor awareness likely influenced measurement."
    if inappropriate in {"N","PN"} and differs in {"N","PN"} and aware in {"N","PN"}:
        return "low", "Outcome measurement appears appropriate and assessor awareness is unlikely."
    return "some_concerns", "Outcome measurement bias cannot be ruled out."

def judge_d5(signals):
    prespec = _r(signals,"analysis_pre_specified")
    mult_m = _r(signals,"multiple_measurements_possible")
    mult_a = _r(signals,"multiple_analyses_possible")
    if mult_m in {"Y","PY"} or mult_a in {"Y","PY"}:
        return "some_concerns", "Selective reporting cannot be ruled out because multiple eligible measurements/analyses may exist."
    if prespec in {"Y","PY"} and mult_m in {"N","PN"} and mult_a in {"N","PN"}:
        return "low", "Result appears consistent with a prespecified analysis."
    return "some_concerns", "Prespecification and selective-reporting risk cannot be fully established."

def overall(domain_judgements):
    vals = [d.judgement for d in domain_judgements]
    if "high" in vals:
        return "high", "At least one domain was judged high risk."
    if vals.count("some_concerns") >= 2:
        return "some_concerns", "Multiple domains raised some concerns."
    if "some_concerns" in vals:
        return "some_concerns", "At least one domain raised some concerns."
    if all(v=="low" for v in vals):
        return "low", "All domains were judged low risk."
    return "unresolved", "Overall risk of bias could not be resolved."
