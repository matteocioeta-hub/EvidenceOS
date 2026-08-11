from __future__ import annotations
import uuid

from .models import (
    BodyOfEvidence, CertaintyAssessment, GRADEDomainJudgement,
    RoB2Assessment, OutcomeResult
)


LEVELS = ["very_low", "low", "moderate", "high"]


def _downgrade(level: str, points: int) -> str:
    idx = LEVELS.index(level)
    return LEVELS[max(0, idx-points)]


class CertaintyEngine:
    @staticmethod
    def assess(
        body: BodyOfEvidence,
        results: list[OutcomeResult],
        rob2_assessments: list[RoB2Assessment],
    ) -> CertaintyAssessment:
        selected_ids = set(body.result_ids)
        relevant_robs = [
            r for r in rob2_assessments
            if (r.result_id is None or r.result_id in selected_ids)
        ]

        # Start high for RCT-focused v0.6.
        start = "high"
        domains = []

        # Risk of bias
        if not relevant_robs:
            rob_j = ("unable_to_assess", 0, "No linked RoB 2 assessments available.")
        else:
            vals = [r.overall_judgement for r in relevant_robs]
            if "high" in vals:
                rob_j = ("serious", 1, "At least one contributing result/report has high overall risk of bias.")
            elif vals.count("some_concerns") >= max(1, len(vals)//2):
                rob_j = ("serious", 1, "Some concerns affect a substantial portion of contributing evidence.")
            elif all(v=="low" for v in vals):
                rob_j = ("not_serious", 0, "Linked RoB 2 assessments are low risk.")
            else:
                rob_j = ("unable_to_assess", 0, "Risk-of-bias contribution is incompletely characterized.")
        domains.append(GRADEDomainJudgement(
            domain="risk_of_bias", judgement=rob_j[0], downgrade=rob_j[1], rationale=rob_j[2]
        ))

        # Inconsistency
        if body.heterogeneity_flag == "high":
            inc = ("serious",1,"Effect directions conflict across contributing results.")
        elif body.heterogeneity_flag == "moderate":
            inc = ("serious",1,"Some inconsistency is present across contributing results.")
        elif body.heterogeneity_flag == "low":
            inc = ("not_serious",0,"Effect directions are broadly consistent.")
        else:
            inc = ("unable_to_assess",0,"Inconsistency cannot be adequately assessed.")
        domains.append(GRADEDomainJudgement(
            domain="inconsistency", judgement=inc[0], downgrade=inc[1], rationale=inc[2]
        ))

        # Indirectness: v0.6 assumes results already grouped to the question; remains conservative
        domains.append(GRADEDomainJudgement(
            domain="indirectness",
            judgement="unable_to_assess",
            downgrade=0,
            rationale="Directness requires explicit study-to-question PICO comparison, which is not yet implemented at body level."
        ))

        # Imprecision
        if body.pooled_ci_lower is not None and body.pooled_ci_upper is not None:
            width = abs(body.pooled_ci_upper - body.pooled_ci_lower)
            if width > 1.5:
                imp = ("serious",1,"Pooled confidence interval is relatively wide; clinical thresholds are not yet modeled.")
            else:
                imp = ("not_serious",0,"Pooled confidence interval is relatively narrow, though clinical thresholds are not yet modeled.")
        else:
            imp = ("unable_to_assess",0,"No compatible pooled confidence interval is available.")
        domains.append(GRADEDomainJudgement(
            domain="imprecision", judgement=imp[0], downgrade=imp[1], rationale=imp[2]
        ))

        # Publication bias
        domains.append(GRADEDomainJudgement(
            domain="publication_bias",
            judgement="unable_to_assess",
            downgrade=0,
            rationale="Publication bias requires dedicated evidence and is not inferred from study count alone."
        ))

        total_down = sum(d.downgrade for d in domains)
        final = _downgrade(start, total_down)

        return CertaintyAssessment(
            certainty_id=f"CERT-{uuid.uuid4().hex[:10].upper()}",
            body_id=body.body_id,
            starting_level=start,
            domains=domains,
            final_level=final,
        )
