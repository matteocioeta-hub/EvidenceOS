from evidenceos.extraction_engine import ExtractionEngine
from evidenceos.rob2_engine import RoB2Engine

TEXT = """METHODS

Potential participants (n = 85) were contacted and 70 signed informed consent.
An investigator who was blinded to all patient characteristics performed a blinded randomization procedure to provide a concealed allocation.
For each group, randomization was performed by applying a computer-generated procedure.

RESULTS

Each intervention arm included 35 participants.

VAS 7 days:
2 months HLL 22 (21), LMC 30 (26), between-group adjusted B 0.2 (95% CI -1.0 to 1.4), p = 0.74.
12 months HLL 24 (27), LMC 25 (22), between-group adjusted B 0.05 (95% CI -1.2 to 1.3), p = 0.94.

RMDQ:
2 months HLL 3.8 (4.0), LMC 3.6 (4.2), between-group adjusted B -0.2 (95% CI -1.3 to 1.0), p = 0.77.
"""

def test_randomized_sample_preferred_over_screened():
    ex = ExtractionEngine().extract("R","Trial",TEXT)
    sample = [f for f in ex.population_fields if f.field_name=="sample_size"][0]
    assert sample.value == 70

def test_adjusted_b_results_extracted():
    ex = ExtractionEngine().extract("R","Trial",TEXT)
    assert len(ex.outcomes) == 3
    pain2 = [r for r in ex.outcomes if r.outcome_name=="Pain intensity" and r.timepoint=="2 months"][0]
    assert pain2.estimate == 0.2
    assert pain2.ci_lower == -1.0
    assert pain2.ci_upper == 1.4
    assert pain2.direction == "no_clear_difference"

def test_randomization_domain_low_with_reported_sequence_and_concealment():
    ex = ExtractionEngine().extract("R","Trial",TEXT)
    rob = RoB2Engine().assess(ex)
    d1 = [d for d in rob.domains if d.domain_id=="D1"][0]
    assert d1.judgement == "low"

def test_patient_reported_pain_can_trigger_high_measurement_bias():
    ex = ExtractionEngine().extract("R","Trial",TEXT)
    pain = [r for r in ex.outcomes if r.outcome_name=="Pain intensity"][0]
    rob = RoB2Engine().assess(ex, result_id=pain.result_id)
    d4 = [d for d in rob.domains if d.domain_id=="D4"][0]
    assert d4.judgement == "high"
