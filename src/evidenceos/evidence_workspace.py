from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field


class StoredStudy(BaseModel):
    report_id: str
    title: str
    design: str
    framework: str | None = None
    trust_overall: str | None = None
    record: dict[str, Any]
    trust_assessment: dict[str, Any]


class SynthesisRequest(BaseModel):
    question: str | None = None
    studies: list[StoredStudy] = Field(min_length=1)


class OutcomeBody(BaseModel):
    outcome: str
    results: int
    studies: int
    directions: dict[str, int]
    dominant_direction: str
    consistency: str
    precision: str
    methodological_support: str
    interpretation: str
    contributing_reports: list[str]


class EvidenceConfidenceProfile(BaseModel):
    quantity: str
    consistency: str
    methodological_trust: str
    precision: str
    directness: str
    overall_label: str
    rationale: list[str]


class SynthesisResponse(BaseModel):
    studies: int
    designs: dict[str, int]
    outcomes: list[OutcomeBody]
    contradictions: list[str]
    gaps: list[str]
    confidence: EvidenceConfidenceProfile
    headline: str
    interpretation_boundary: str


def _field_value(field: Any) -> Any:
    if not isinstance(field, dict):
        return None
    return field.get("value")


def _direction(result: dict[str, Any]) -> str:
    value = _field_value(result.get("direction"))
    return str(value or "uncertain")


def _outcome(result: dict[str, Any]) -> str:
    value = _field_value(result.get("outcome"))
    return str(value or "Unspecified outcome").strip() or "Unspecified outcome"


def _trust_rank(study: StoredStudy) -> int:
    """
    This is not a risk-of-bias score. It only ranks how resolved the current
    EvidenceOS appraisal is for body-level descriptive summarisation.
    """
    value = (study.trust_overall or "").lower()
    if value in {"low", "substantial_information_available"}:
        return 3
    if value in {"some_concerns", "outcome_specific"}:
        return 2
    if value in {"high"}:
        return 1
    return 0


def _precision_for_results(results: list[dict[str, Any]]) -> str:
    with_ci = 0
    total = 0
    for r in results:
        total += 1
        lo = _field_value(r.get("ci_lower"))
        hi = _field_value(r.get("ci_upper"))
        if lo is not None and hi is not None:
            with_ci += 1
    if total == 0:
        return "not_assessable"
    ratio = with_ci / total
    if ratio >= 0.75:
        return "mostly_available"
    if ratio >= 0.25:
        return "partially_available"
    return "mostly_unavailable"


def synthesize(req: SynthesisRequest) -> SynthesisResponse:
    designs = Counter(s.design for s in req.studies)
    grouped: dict[str, list[tuple[StoredStudy, dict[str, Any]]]] = defaultdict(list)

    for study in req.studies:
        for result in study.record.get("results", []) or []:
            grouped[_outcome(result)].append((study, result))

    bodies: list[OutcomeBody] = []
    contradictions: list[str] = []
    gaps: list[str] = []

    for outcome, pairs in sorted(grouped.items(), key=lambda x: (-len(x[1]), x[0].lower())):
        dirs = Counter(_direction(r) for _, r in pairs)
        known_dirs = {k: v for k, v in dirs.items() if k != "uncertain" and v > 0}

        if not known_dirs:
            dominant = "uncertain"
            consistency = "not_assessable"
        elif len(known_dirs) == 1:
            dominant = max(known_dirs, key=known_dirs.get)
            consistency = "consistent"
        else:
            dominant = max(known_dirs, key=known_dirs.get)
            total_known = sum(known_dirs.values())
            dominant_share = known_dirs[dominant] / total_known
            consistency = "mixed" if dominant_share < 0.75 else "mostly_consistent"
            if "favours_intervention" in known_dirs and "favours_comparator" in known_dirs:
                contradictions.append(
                    f"{outcome}: results include effects in opposite directions."
                )
            elif "no_clear_difference" in known_dirs and len(known_dirs) > 1:
                contradictions.append(
                    f"{outcome}: positive/negative directional findings coexist with no-clear-difference results."
                )

        results_only = [r for _, r in pairs]
        precision = _precision_for_results(results_only)
        ranks = [_trust_rank(s) for s, _ in pairs]
        avg_rank = sum(ranks) / len(ranks) if ranks else 0
        if avg_rank >= 2.5:
            method = "relatively_well_characterized"
        elif avg_rank >= 1.5:
            method = "partially_characterized"
        else:
            method = "insufficiently_characterized"

        study_count = len({s.report_id for s, _ in pairs})
        if study_count == 1:
            interpretation = "Evidence for this outcome comes from a single analysed study."
        elif consistency == "consistent":
            interpretation = f"{study_count} analysed studies/results show a broadly consistent direction."
        elif consistency in {"mixed", "mostly_consistent"}:
            interpretation = f"The analysed evidence is heterogeneous; the dominant direction should be qualified."
        else:
            interpretation = "The available extracted results do not support a directional conclusion."

        bodies.append(OutcomeBody(
            outcome=outcome,
            results=len(pairs),
            studies=study_count,
            directions=dict(dirs),
            dominant_direction=dominant,
            consistency=consistency,
            precision=precision,
            methodological_support=method,
            interpretation=interpretation,
            contributing_reports=list(dict.fromkeys(s.report_id for s, _ in pairs)),
        ))

    if not bodies:
        gaps.append("No outcome-level result was deterministically extracted from the stored PDFs.")
    else:
        singletons = [b.outcome for b in bodies if b.studies == 1]
        if singletons:
            gaps.append(
                "Several outcomes are currently represented by only one analysed study: "
                + ", ".join(singletons[:6])
                + ("." if len(singletons) <= 6 else ", …")
            )
        if all(b.precision == "mostly_unavailable" for b in bodies):
            gaps.append("Confidence intervals/precision information is largely unavailable in the extracted evidence.")
        if any(b.consistency in {"mixed", "mostly_consistent"} for b in bodies):
            gaps.append("Some outcomes contain inconsistent directional evidence that needs explanation.")

    n = len(req.studies)
    quantity = "limited" if n <= 2 else "moderate" if n <= 5 else "substantial"

    consist_vals = [b.consistency for b in bodies]
    if not consist_vals:
        consistency_global = "not_assessable"
    elif any(x == "mixed" for x in consist_vals):
        consistency_global = "concerns"
    elif all(x == "consistent" for x in consist_vals):
        consistency_global = "broadly_consistent"
    else:
        consistency_global = "partially_consistent"

    trust_ranks = [_trust_rank(s) for s in req.studies]
    if trust_ranks and sum(trust_ranks) / len(trust_ranks) >= 2.5:
        methodological = "relatively_well_characterized"
    elif trust_ranks and sum(trust_ranks) / len(trust_ranks) >= 1.5:
        methodological = "partially_characterized"
    else:
        methodological = "insufficiently_characterized"

    precisions = [b.precision for b in bodies]
    if precisions and all(p == "mostly_available" for p in precisions):
        precision_global = "mostly_available"
    elif precisions and any(p == "mostly_available" for p in precisions):
        precision_global = "partial"
    else:
        precision_global = "limited"

    # Directness needs explicit study-to-question mapping; do not infer it from titles.
    directness = "not_yet_assessed"

    concerns = 0
    concerns += quantity == "limited"
    concerns += consistency_global in {"concerns", "not_assessable"}
    concerns += methodological == "insufficiently_characterized"
    concerns += precision_global == "limited"
    concerns += directness == "not_yet_assessed"

    if concerns <= 1:
        overall = "more_resolved"
    elif concerns <= 3:
        overall = "partially_resolved"
    else:
        overall = "substantially_uncertain"

    rationale = [
        f"{n} analysed full-text study/studies are currently stored.",
        f"Body-level consistency: {consistency_global}.",
        f"Methodological appraisal information: {methodological}.",
        f"Precision information: {precision_global}.",
        "Directness is intentionally not inferred until study-to-question PICO mapping is implemented.",
    ]

    if not bodies:
        headline = "EvidenceOS cannot yet form an outcome-level body of evidence."
    elif contradictions:
        headline = "The current body of evidence contains important contradictions."
    elif consistency_global == "broadly_consistent":
        headline = "The analysed evidence shows a broadly consistent pattern."
    else:
        headline = "The current evidence pattern is only partially resolved."

    return SynthesisResponse(
        studies=n,
        designs=dict(designs),
        outcomes=bodies,
        contradictions=contradictions,
        gaps=gaps,
        confidence=EvidenceConfidenceProfile(
            quantity=quantity,
            consistency=consistency_global,
            methodological_trust=methodological,
            precision=precision_global,
            directness=directness,
            overall_label=overall,
            rationale=rationale,
        ),
        headline=headline,
        interpretation_boundary=(
            "This synthesis includes only PDFs explicitly analysed and saved in this browser workspace. "
            "It is not a systematic review, meta-analysis or GRADE assessment. EvidenceOS does not pool "
            "incompatible outcomes/designs and does not infer missing directness or publication-bias information."
        ),
    )
