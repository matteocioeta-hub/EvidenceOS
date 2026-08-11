from fastapi.testclient import TestClient

from evidenceos import __version__, ExtractionEngineV1
from evidenceos.api import app

DEMO = """
Participants were randomly assigned to HIT or MIT.
Thirty-eight participants were included in the initial PRE-POST analysis, HIT n = 19 and MIT n = 19.
Finally, 29 participants were included in the follow-up analysis, HIT n = 16 and MIT n = 13.
Pain intensity, NPRS 0-10:
HIT PRE 5.6 (1.5), POST 2.6 (1.3), FU 2.3 (2.1).
MIT PRE 5.0 (1.7), POST 3.5 (1.7), FU 2.3 (1.1).
Difference of deltas PRE to FU between HIT and MIT: 0.5, not significant.
"""

def test_version():
    assert __version__ == "0.1.0a1"

def test_public_engine():
    record = ExtractionEngineV1().extract("D", "Demo", DEMO)
    rnd = next(s for s in record.sample_sets if s.role == "randomized")
    ana = next(s for s in record.sample_sets if s.role == "analysed")
    assert rnd.total_n.value == 38
    assert ana.total_n.value == 29
    assert any(a.code == "ATTRITION_PRESENT" for a in record.alarms)

def test_health_api():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0a1"

def test_extract_api():
    client = TestClient(app)
    response = client.post("/v1/extract", json={
        "report_id": "D",
        "title": "Demo",
        "text": DEMO,
    })
    assert response.status_code == 200
    assert response.json()["record"]["report_id"] == "D"
