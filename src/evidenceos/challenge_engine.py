from __future__ import annotations
import uuid
from collections import Counter

from .models import (
    ChallengeAssessment,
    ChallengeDimensionResult,
    CalibratedConclusion,
    CanonicalClaim,
    BodyOfEvidence,
    OutcomeResult,
    RoB2Assessment,
)


def _result_map(results):
    return {r.result_id: r for r in results}


class ChallengeEngine:
    """
    Adversarial reasoning over evidence already present in the corpus.

    v0.7 does NOT yet launch new external searches. It asks:
    "Given what we already retrieved, what could materially weaken this conclusion?"
    """

    def assess(
        self,
        conclusion: CalibratedConclusion,
        claim: CanonicalClaim,
        body: BodyOfEvidence,
        all_results: list[OutcomeResult],
        rob2_assessments: list[RoB2Assessment],
        all_claims: list[CanonicalClaim] | None = None,
    ) -> ChallengeAssessment:

        dimensions = []
        body_ids = set(body.result_ids)
        body_results = [r for r in all_results if r.result_id in body_ids]
        other_results = [r for r in all_results if r.result_id not in body_ids]

        # 1. Contradictory evidence within same body
        opposite = []
        if body.effect_direction == "favours_intervention":
            opposite = [r for r in body_results if r.direction in {"favours_comparator","no_clear_difference"}]
        elif body.effect_direction == "favours_comparator":
            opposite = [r for r in body_results if r.direction in {"favours_intervention","no_clear_difference"}]

        if opposite:
            severity = "material" if len(opposite) >= max(1, len(body_results)//3) else "minor"
            dimensions.append(ChallengeDimensionResult(
                dimension="contradictory_evidence",
                triggered=True,
                severity=severity,
                rationale=f"{len(opposite)} contributing result(s) do not support the dominant direction.",
                related_result_ids=[r.result_id for r in opposite],
            ))
        else:
            dimensions.append(ChallengeDimensionResult(
                dimension="contradictory_evidence",
                triggered=False,
                severity="none",
                rationale="No materially contradictory contributing result was identified within this body of evidence."
            ))

        # 2. Active comparator challenge: same population/intervention/outcome but different comparator
        active_like = []
        for c in (all_claims or []):
            if c.claim_id == claim.claim_id:
                continue
            if (
                c.population == claim.population and
                c.intervention == claim.intervention and
                c.outcome == claim.outcome and
                c.timepoint == claim.timepoint and
                c.comparator != claim.comparator
            ):
                active_like.extend(c.result_ids)

        if active_like:
            dimensions.append(ChallengeDimensionResult(
                dimension="active_comparator",
                triggered=True,
                severity="material",
                rationale="A materially different comparator is represented for the same population, intervention, outcome, and timepoint.",
                related_result_ids=list(dict.fromkeys(active_like)),
            ))
        else:
            dimensions.append(ChallengeDimensionResult(
                dimension="active_comparator",
                triggered=False,
                severity="none",
                rationale="No alternative comparator body was identified for the same P-I-O-time unit."
            ))

        # 3. Timepoint challenge: same P-I-C-O but different timepoint
        time_related = []
        for c in (all_claims or []):
            if c.claim_id == claim.claim_id:
                continue
            if (
                c.population == claim.population and
                c.intervention == claim.intervention and
                c.comparator == claim.comparator and
                c.outcome == claim.outcome and
                c.timepoint != claim.timepoint
            ):
                time_related.extend(c.result_ids)

        if time_related:
            dimensions.append(ChallengeDimensionResult(
                dimension="timepoint",
                triggered=True,
                severity="minor",
                rationale="Evidence exists at other timepoints; durability or timing of effect should be checked before generalizing.",
                related_result_ids=list(dict.fromkeys(time_related)),
            ))
        else:
            dimensions.append(ChallengeDimensionResult(
                dimension="timepoint",
                triggered=False,
                severity="none",
                rationale="No alternative timepoint evidence was identified in the supplied corpus."
            ))

        # 4. Risk-of-bias asymmetry
        rob_map = {}
        for a in rob2_assessments:
            if a.result_id:
                rob_map[a.result_id] = a

        supporting_ids = []
        contrary_ids = []
        for r in body_results:
            if body.effect_direction == "favours_intervention":
                (supporting_ids if r.direction=="favours_intervention" else contrary_ids).append(r.result_id)
            elif body.effect_direction == "favours_comparator":
                (supporting_ids if r.direction=="favours_comparator" else contrary_ids).append(r.result_id)

        high_support = [rid for rid in supporting_ids if rob_map.get(rid) and rob_map[rid].overall_judgement=="high"]
        low_support = [rid for rid in supporting_ids if rob_map.get(rid) and rob_map[rid].overall_judgement=="low"]

        if high_support and not low_support:
            dimensions.append(ChallengeDimensionResult(
                dimension="risk_of_bias_asymmetry",
                triggered=True,
                severity="material",
                rationale="Support for the dominant effect appears concentrated in high-risk-of-bias results.",
                related_result_ids=high_support,
                related_assessment_ids=[rob_map[rid].assessment_id for rid in high_support],
            ))
        else:
            dimensions.append(ChallengeDimensionResult(
                dimension="risk_of_bias_asymmetry",
                triggered=False,
                severity="none",
                rationale="No clear asymmetry indicating that the dominant conclusion is driven only by high-risk-of-bias evidence."
            ))

        # 5. Higher-quality contradictory evidence
        high_quality_contrary = []
        for rid in contrary_ids:
            a = rob_map.get(rid)
            if a and a.overall_judgement == "low":
                high_quality_contrary.append(rid)

        if high_quality_contrary:
            dimensions.append(ChallengeDimensionResult(
                dimension="higher_quality_evidence",
                triggered=True,
                severity="critical",
                rationale="Low-risk-of-bias evidence contradicts the dominant effect direction.",
                related_result_ids=high_quality_contrary,
                related_assessment_ids=[rob_map[rid].assessment_id for rid in high_quality_contrary],
            ))
        else:
            dimensions.append(ChallengeDimensionResult(
                dimension="higher_quality_evidence",
                triggered=False,
                severity="none",
                rationale="No low-risk-of-bias contradictory result was identified."
            ))

        # 6. Newer evidence placeholder from available metadata not yet implemented
        dimensions.append(ChallengeDimensionResult(
            dimension="newer_evidence",
            triggered=False,
            severity="none",
            rationale="v0.7 does not yet execute a dedicated newer-evidence search."
        ))

        # 7. Indirectness placeholder
        dimensions.append(ChallengeDimensionResult(
            dimension="indirectness",
            triggered=False,
            severity="none",
            rationale="Explicit study-to-question directness comparison is not yet available in v0.7."
        ))

        critical = [d for d in dimensions if d.severity=="critical" and d.triggered]
        material = [d for d in dimensions if d.severity=="material" and d.triggered]
        minor = [d for d in dimensions if d.severity=="minor" and d.triggered]

        if critical:
            verdict = "materially_weakened"
            revised = f"{conclusion.text.rstrip('.')} However, higher-quality contradictory evidence materially weakens this conclusion."
            rationale = "At least one critical adversarial signal was identified."
        elif len(material) >= 2:
            verdict = "materially_weakened"
            revised = f"{conclusion.text.rstrip('.')} Important qualifications are required because multiple material challenges were identified."
            rationale = "Multiple material challenge dimensions were triggered."
        elif material or minor:
            verdict = "survived_with_qualification"
            revised = f"{conclusion.text.rstrip('.')} This conclusion should be qualified in light of the identified challenge evidence."
            rationale = "The conclusion remains plausible but requires qualification."
        elif not body_results:
            verdict = "insufficient_evidence_to_challenge"
            revised = None
            rationale = "No result-level evidence was available to challenge the conclusion."
        else:
            verdict = "survived"
            revised = conclusion.text
            rationale = "No material adversarial signal was identified in the supplied corpus."

        prov = []
        for d in dimensions:
            prov.extend(d.related_result_ids)
        prov = list(dict.fromkeys(prov))

        return ChallengeAssessment(
            challenge_id=f"CHAL-{uuid.uuid4().hex[:10].upper()}",
            conclusion_id=conclusion.conclusion_id,
            verdict=verdict,
            dimensions=dimensions,
            revised_conclusion=revised,
            rationale=rationale,
            provenance_result_ids=prov,
        )
