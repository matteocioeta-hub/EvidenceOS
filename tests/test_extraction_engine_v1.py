from evidenceos.extraction_engine_v1 import ExtractionEngineV1
from evidenceos.evidence_schema_v1 import UniversalEvidenceRecord

VERB = """Participants with chronic nonspecific low back pain were randomly assigned to an experimental high intensity training group (HIT) or a moderate intensity training control group (MIT).
Thirty-eight participants were included in the initial PRE-POST analysis, HIT n = 19 and MIT n = 19.
Finally, 29 participants were included in the follow-up analysis, HIT n = 16 and MIT n = 13.
Disability, MODI %:
HIT PRE 20.9 (8.7), POST 7.5 (5.4), FU 7.9 (8.4).
MIT PRE 16.2 (8.2), POST 10.6 (3.0), FU 10.4 (9.6).
Difference of deltas PRE to FU between HIT and MIT: 3.6, significant in favour of HIT.
Pain intensity, NPRS 0-10:
HIT PRE 5.6 (1.5), POST 2.6 (1.3), FU 2.3 (2.1).
MIT PRE 5.0 (1.7), POST 3.5 (1.7), FU 2.3 (1.1).
Difference of deltas PRE to FU between HIT and MIT: 0.5, not significant.
"""

def test_arm_reconstruction():
    r=ExtractionEngineV1().extract("V","Trial",VERB)
    rnd=next(s for s in r.sample_sets if s.role=="randomized")
    assert rnd.total_n.value==38
    assert sum(a.n.value for a in rnd.arms)==38

def test_randomized_vs_analysed_separate():
    r=ExtractionEngineV1().extract("V","Trial",VERB)
    assert next(s for s in r.sample_sets if s.role=="randomized").total_n.value==38
    assert next(s for s in r.sample_sets if s.role=="analysed").total_n.value==29
    assert any(a.code=="ATTRITION_PRESENT" for a in r.alarms)

def test_outcome_mapping():
    r=ExtractionEngineV1().extract("V","Trial",VERB)
    assert len(r.results)==2
    pain=next(x for x in r.results if x.outcome.value=="Pain intensity")
    dis=next(x for x in r.results if x.outcome.value=="Disability")
    assert pain.significance.value is False
    assert pain.direction.value=="no_clear_difference"
    assert dis.significance.value is True
    assert dis.direction.value=="favours_intervention"

def test_all_direct_fields_grounded():
    r=ExtractionEngineV1().extract("V","Trial",VERB)
    assert all(x.status in ("verified","derived") for s in r.sample_sets for x in ([s.total_n] if s.total_n else []))

def test_schema_serializes():
    r=ExtractionEngineV1().extract("V","Trial",VERB)
    UniversalEvidenceRecord.model_validate(r.model_dump())
