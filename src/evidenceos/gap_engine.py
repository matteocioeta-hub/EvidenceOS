from __future__ import annotations

from .gap_detector import GapDetector
from .construct_checker import ConstructChecker
from .gap_falsifier import GapFalsifier
from .research_opportunity_engine import ResearchOpportunityEngine
from .models import GapEngineResponse


class GapEngine:
    def analyse(self, question, claims, bodies, conclusions, challenges):
        hypotheses = GapDetector.detect(claims, bodies, conclusions, challenges)
        construct_checks = []
        all_evidence = []
        falsifications = []
        final_gaps = []
        opportunities = []

        for gap in hypotheses:
            check = ConstructChecker.check(gap)
            construct_checks.append(check)

            evidence = GapFalsifier.build_evidence(gap, bodies, claims)
            all_evidence.extend(evidence)

            fals = GapFalsifier.assess(gap, evidence, construct_ambiguity=check.ambiguity)
            falsifications.append(fals)

            final = ResearchOpportunityEngine.final_gap(gap, fals)
            final_gaps.append(final)

            opp = ResearchOpportunityEngine.opportunity(final)
            if opp:
                opportunities.append(opp)

        return GapEngineResponse(
            hypotheses=hypotheses,
            construct_checks=construct_checks,
            gap_evidence=all_evidence,
            falsifications=falsifications,
            final_gaps=final_gaps,
            research_opportunities=opportunities,
        )
