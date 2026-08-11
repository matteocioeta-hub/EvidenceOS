from __future__ import annotations
import re
from .models import CanonicalRecord, DesignPrediction

def _haystack(record):
    return " ".join([record.title or "", record.abstract or "", " ".join(record.publication_types or [])]).lower()

class StudyDesignClassifier:
    @staticmethod
    def classify(record: CanonicalRecord) -> DesignPrediction:
        text=_haystack(record); ptypes=" ".join(record.publication_types or []).lower()
        if "randomized controlled trial" in ptypes:
            return DesignPrediction(final_label="randomized_controlled_trial",confidence=.99,method="rules",rationale="Publication type explicitly identifies an RCT.")
        if "meta-analysis" in ptypes:
            return DesignPrediction(final_label="meta_analysis",confidence=.99,method="rules",rationale="Publication type explicitly identifies a meta-analysis.")
        if "systematic review" in ptypes:
            return DesignPrediction(final_label="systematic_review",confidence=.99,method="rules",rationale="Publication type explicitly identifies a systematic review.")
        rules=[
            ("meta_analysis",[r"\bmeta-analysis\b",r"\bmeta analysis\b"],.98,"Meta-analysis terminology detected."),
            ("systematic_review",[r"\bsystematic review\b",r"\bscoping review\b",r"\bumbrella review\b"],.97,"Systematic-review terminology detected."),
            ("protocol",[r"\bstudy protocol\b",r"\btrial protocol\b",r"\bsystematic review protocol\b"],.96,"Protocol terminology detected."),
            ("randomized_controlled_trial",[r"\brandomi[sz]ed controlled trial\b",r"\brandomly assigned\b",r"\brandom allocation\b"],.95,"Randomization terminology detected."),
            ("qualitative",[r"\bqualitative study\b",r"\bthematic analysis\b",r"\bgrounded theory\b",r"\bsemi-structured interview"],.92,"Qualitative-method terminology detected."),
            ("cross_sectional",[r"\bcross-sectional\b",r"\bcross sectional\b"],.92,"Cross-sectional terminology detected."),
            ("case_control",[r"\bcase-control\b",r"\bcase control\b"],.92,"Case-control terminology detected."),
            ("cohort",[r"\bprospective cohort\b",r"\bretrospective cohort\b",r"\bcohort study\b"],.90,"Cohort terminology detected."),
            ("guideline",[r"\bclinical practice guideline\b",r"\bguideline\b"],.90,"Guideline terminology detected.")
        ]
        for label,patterns,conf,rat in rules:
            if any(re.search(p,text,re.I) for p in patterns):
                return DesignPrediction(final_label=label,confidence=conf,method="rules",rationale=rat)
        if any(x in text for x in ["intervention study","controlled trial","clinical trial"]):
            return DesignPrediction(final_label="nonrandomized_intervention",confidence=.65,method="rules",rationale="Intervention terminology detected without clear randomization.")
        return DesignPrediction(final_label="uncertain",confidence=.40,method="rules",rationale="No sufficiently specific study-design signal detected.")
