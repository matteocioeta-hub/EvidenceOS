from .semantic_extractor_v1 import SemanticExtractorV1
from .evidence_verifier_v1 import EvidenceVerifierV1
from .consistency_engine_v1 import ConsistencyEngineV1

class ExtractionEngineV1:
    def extract(self, report_id, title, text):
        proposal=SemanticExtractorV1.extract(report_id,title,text)
        verified=EvidenceVerifierV1.verify(proposal,text)
        return ConsistencyEngineV1.run(verified)
