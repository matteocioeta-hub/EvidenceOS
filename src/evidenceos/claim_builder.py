from __future__ import annotations
import uuid
from collections import defaultdict

from .models import StructuredQuestion, OutcomeResult, CanonicalClaim


def _normalize_timepoint(value: str | None) -> str:
    if not value:
        return "unspecified_timepoint"
    return value.strip().lower()


class ClaimBuilder:
    @staticmethod
    def build(question: StructuredQuestion, results: list[OutcomeResult]) -> list[CanonicalClaim]:
        groups = defaultdict(list)

        comparator = question.comparator.label if question.comparator.specified else "unspecified comparator"
        population = question.population.label
        intervention = question.intervention.label

        for r in results:
            key = (
                population,
                intervention,
                comparator,
                r.outcome_name or "unspecified outcome",
                _normalize_timepoint(r.timepoint),
            )
            groups[key].append(r)

        claims = []
        for (pop, inter, comp, out, time), rs in groups.items():
            text = f"{inter} affects {out} compared with {comp} in {pop} at {time}."
            claims.append(
                CanonicalClaim(
                    claim_id=f"CLAIM-{uuid.uuid4().hex[:10].upper()}",
                    population=pop,
                    intervention=inter,
                    comparator=comp,
                    outcome=out,
                    timepoint=time,
                    canonical_text=text,
                    result_ids=[r.result_id for r in rs],
                )
            )
        return claims
