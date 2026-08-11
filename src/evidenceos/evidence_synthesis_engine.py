from __future__ import annotations

from .models import EvidenceSynthesisResponse
from .claim_builder import ClaimBuilder
from .body_of_evidence_engine import BodyOfEvidenceEngine
from .certainty_engine import CertaintyEngine
from .conclusion_calibrator import ConclusionCalibrator


class EvidenceSynthesisEngine:
    def synthesize(self, question, results, rob2_assessments):
        claims = ClaimBuilder.build(question, results)
        bodies = []
        certs = []
        conclusions = []

        for claim in claims:
            body = BodyOfEvidenceEngine.build(claim, results)
            cert = CertaintyEngine.assess(body, results, rob2_assessments)
            conclusion = ConclusionCalibrator.build(claim, body, cert)
            bodies.append(body)
            certs.append(cert)
            conclusions.append(conclusion)

        return EvidenceSynthesisResponse(
            claims=claims,
            bodies_of_evidence=bodies,
            certainty_assessments=certs,
            conclusions=conclusions,
        )
