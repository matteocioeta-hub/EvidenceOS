from __future__ import annotations
import uuid
from collections import defaultdict

from .models import GapHypothesis, BodyOfEvidence, CanonicalClaim, CalibratedConclusion, ChallengeAssessment


class GapDetector:
    """
    Conservative gap hypothesis generator from existing evidence state.

    It generates hypotheses, not conclusions.
    """

    @staticmethod
    def detect(
        claims: list[CanonicalClaim],
        bodies: list[BodyOfEvidence],
        conclusions: list[CalibratedConclusion],
        challenges: list[ChallengeAssessment],
    ) -> list[GapHypothesis]:
        gaps = []
        body_by_claim = {b.claim_id: b for b in bodies}
        conclusion_by_claim = {c.claim_id: c for c in conclusions}
        challenge_by_conclusion = {c.conclusion_id: c for c in challenges}

        # Quantity / precision / consistency / temporal hypotheses
        for claim in claims:
            body = body_by_claim.get(claim.claim_id)
            conc = conclusion_by_claim.get(claim.claim_id)
            if not body:
                continue

            if body.unique_studies <= 1:
                gaps.append(GapHypothesis(
                    gap_hypothesis_id=f"GAP-{uuid.uuid4().hex[:10].upper()}",
                    topic=claim.outcome,
                    statement=f"Evidence addressing {claim.outcome} at {claim.timepoint} may be sparse.",
                    initial_gap_type="quantity",
                    status="hypothesized",
                    detected_from=[body.body_id],
                ))

            if body.total_participants is not None and body.total_participants < 400:
                gaps.append(GapHypothesis(
                    gap_hypothesis_id=f"GAP-{uuid.uuid4().hex[:10].upper()}",
                    topic=claim.outcome,
                    statement=f"Evidence for {claim.outcome} at {claim.timepoint} may be imprecise because the total sample is limited.",
                    initial_gap_type="precision",
                    status="hypothesized",
                    detected_from=[body.body_id],
                ))

            if body.heterogeneity_flag in {"moderate","high"}:
                gaps.append(GapHypothesis(
                    gap_hypothesis_id=f"GAP-{uuid.uuid4().hex[:10].upper()}",
                    topic=claim.outcome,
                    statement=f"Evidence for {claim.outcome} at {claim.timepoint} is inconsistent and may require explanation.",
                    initial_gap_type="consistency",
                    status="hypothesized",
                    detected_from=[body.body_id],
                ))

        # Temporal coverage across same P-I-C-O
        groups = defaultdict(set)
        group_claims = defaultdict(list)
        for claim in claims:
            key = (claim.population, claim.intervention, claim.comparator, claim.outcome)
            groups[key].add(claim.timepoint)
            group_claims[key].append(claim)

        for key, times in groups.items():
            if len(times) == 1:
                pop, inter, comp, out = key
                only_time = next(iter(times))
                gaps.append(GapHypothesis(
                    gap_hypothesis_id=f"GAP-{uuid.uuid4().hex[:10].upper()}",
                    topic=out,
                    statement=f"Evidence for {out} is concentrated at {only_time}; durability across other follow-up periods may be insufficiently characterized.",
                    initial_gap_type="temporal",
                    status="hypothesized",
                    detected_from=[c.claim_id for c in group_claims[key]],
                ))

        # Comparator hypothesis: only one comparator represented
        by_pio = defaultdict(set)
        by_pio_claims = defaultdict(list)
        for claim in claims:
            key = (claim.population, claim.intervention, claim.outcome, claim.timepoint)
            by_pio[key].add(claim.comparator)
            by_pio_claims[key].append(claim)

        for key, comps in by_pio.items():
            if len(comps) == 1:
                pop, inter, out, time = key
                comp = next(iter(comps))
                gaps.append(GapHypothesis(
                    gap_hypothesis_id=f"GAP-{uuid.uuid4().hex[:10].upper()}",
                    topic=out,
                    statement=f"Comparative effectiveness for {out} at {time} may be undercharacterized because evidence is concentrated against {comp}.",
                    initial_gap_type="comparator",
                    status="hypothesized",
                    detected_from=[c.claim_id for c in by_pio_claims[key]],
                ))

        return gaps
