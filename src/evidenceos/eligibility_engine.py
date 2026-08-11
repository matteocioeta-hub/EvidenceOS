from __future__ import annotations
import re
from .models import StructuredQuestion, CanonicalRecord, DesignPrediction, EligibilityDimension, EligibilityPrediction

def _norm(s):
    s=(s or "").lower(); s=re.sub(r"[^a-z0-9\s]"," ",s); return re.sub(r"\s+"," ",s).strip()

def _contains_any(text,terms):
    n=_norm(text); return any(_norm(t) in n for t in terms if t)

class EligibilityEngine:
    ALLOWED_DESIGNS={"randomized_controlled_trial","systematic_review","meta_analysis"}
    @classmethod
    def predict(cls,question,record,design):
        text=" ".join([record.title or "",record.abstract or ""]); pop=[question.population.label,*question.population.concepts]; inter=[question.intervention.label,*question.intervention.concepts]; outs=[o.label for o in question.outcomes]
        pm=_contains_any(text,pop); im=_contains_any(text,inter); om=_contains_any(text,outs) if outs else False
        dims=[
            EligibilityDimension(dimension="population",judgement="match" if pm else "uncertain",rationale="Population terminology found." if pm else "Population not clearly identifiable from title/abstract."),
            EligibilityDimension(dimension="intervention",judgement="match" if im else "uncertain",rationale="Intervention terminology found." if im else "Intervention not clearly identifiable from title/abstract."),
            EligibilityDimension(dimension="comparator",judgement="not_required",rationale="Comparator is not required for title/abstract inclusion in v0.3."),
            EligibilityDimension(dimension="outcome",judgement="match" if om else "not_required",rationale="Outcome terminology found." if om else "Outcome is not required for title/abstract inclusion in v0.3."),
            EligibilityDimension(dimension="design",judgement="match" if design.final_label in cls.ALLOWED_DESIGNS else ("uncertain" if design.final_label=="uncertain" else "mismatch"),rationale=f"Detected design: {design.final_label}.")
        ]
        if design.final_label not in cls.ALLOWED_DESIGNS and design.final_label!="uncertain":
            return EligibilityPrediction(record_id=record.record_id,overall="exclude",confidence=max(.85,design.confidence),dimensions=dims,method="rules",exclusion_reason=f"Unsupported study design for v0.3: {design.final_label}")
        if pm and im and design.final_label in cls.ALLOWED_DESIGNS:
            return EligibilityPrediction(record_id=record.record_id,overall="include",confidence=min(.99,.75+.1*int(om)+.1*design.confidence),dimensions=dims,method="rules")
        if design.final_label in cls.ALLOWED_DESIGNS and (pm or im):
            return EligibilityPrediction(record_id=record.record_id,overall="uncertain",confidence=.60,dimensions=dims,method="rules")
        return EligibilityPrediction(record_id=record.record_id,overall="uncertain",confidence=.45,dimensions=dims,method="rules")
