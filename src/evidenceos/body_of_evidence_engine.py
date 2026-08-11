from __future__ import annotations
import math, uuid
from collections import Counter

from .models import CanonicalClaim, OutcomeResult, BodyOfEvidence


def _direction(results):
    dirs = [r.direction for r in results if r.direction != "uncertain"]
    if not dirs:
        return "uncertain"
    counts = Counter(dirs)
    if counts["favours_intervention"] and counts["favours_comparator"]:
        return "mixed"
    if counts["favours_intervention"] and counts["no_clear_difference"]:
        return "mixed"
    if counts["favours_comparator"] and counts["no_clear_difference"]:
        return "mixed"
    return counts.most_common(1)[0][0]


def _simple_inverse_variance_pool(results):
    usable = []
    for r in results:
        if r.estimate is None or r.ci_lower is None or r.ci_upper is None:
            continue
        if not r.effect_measure:
            continue
        se = (r.ci_upper - r.ci_lower) / (2 * 1.96)
        if se <= 0:
            continue
        usable.append((r, se))
    if not usable:
        return None
    measures = {r.effect_measure for r, _ in usable}
    if len(measures) != 1:
        return None
    weights = [1/(se**2) for _, se in usable]
    estimate = sum(w*r.estimate for w,(r,se) in zip(weights,usable))/sum(weights)
    se_pool = math.sqrt(1/sum(weights))
    return {
        "measure": next(iter(measures)),
        "estimate": estimate,
        "lower": estimate - 1.96*se_pool,
        "upper": estimate + 1.96*se_pool,
    }


class BodyOfEvidenceEngine:
    @staticmethod
    def build(claim: CanonicalClaim, results: list[OutcomeResult]) -> BodyOfEvidence:
        selected = [r for r in results if r.result_id in set(claim.result_ids)]
        reports = {r.report_id for r in selected}
        studies = {r.study_id or r.report_id for r in selected}
        n_total = 0
        has_n = False
        for r in selected:
            if r.n_intervention is not None:
                n_total += r.n_intervention
                has_n = True
            if r.n_comparator is not None:
                n_total += r.n_comparator
                has_n = True

        pooled = _simple_inverse_variance_pool(selected)

        directions = [r.direction for r in selected if r.direction != "uncertain"]
        heterogeneity = "unknown"
        if len(directions) >= 2:
            uniq = set(directions)
            if len(uniq) == 1:
                heterogeneity = "low"
            elif "favours_intervention" in uniq and "favours_comparator" in uniq:
                heterogeneity = "high"
            else:
                heterogeneity = "moderate"

        return BodyOfEvidence(
            body_id=f"BOE-{uuid.uuid4().hex[:10].upper()}",
            claim_id=claim.claim_id,
            result_ids=claim.result_ids,
            unique_reports=len(reports),
            unique_studies=len(studies),
            total_participants=n_total if has_n else None,
            compatible_effect_measure=pooled["measure"] if pooled else None,
            pooled_estimate=pooled["estimate"] if pooled else None,
            pooled_ci_lower=pooled["lower"] if pooled else None,
            pooled_ci_upper=pooled["upper"] if pooled else None,
            effect_direction=_direction(selected),
            heterogeneity_flag=heterogeneity,
        )
