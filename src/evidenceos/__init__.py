"""EvidenceOS — auditable evidence extraction and epistemic verification."""

__version__ = "0.1.0a1"

from .extraction_engine_v1 import ExtractionEngineV1
from .evidence_schema_v1 import UniversalEvidenceRecord

__all__ = ["ExtractionEngineV1", "UniversalEvidenceRecord", "__version__"]
