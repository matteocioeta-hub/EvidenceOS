from __future__ import annotations
import re, math
from .evidence_schema_v1 import *

def normnum(x):
    try: return float(x)
    except: return None

class EvidenceVerifierV1:
    @staticmethod
    def verify(rec: UniversalEvidenceRecord, source_text: str) -> UniversalEvidenceRecord:
        # Verify provenance quotes literally occur in source.
        def check_field(f):
            if f is None: return
            if f.status == "derived":
                return
            if not f.provenance:
                f.status="unverified"; f.confidence=min(f.confidence,.25); return
            if not any(p.quote in source_text for p in f.provenance):
                f.status="unverified"; f.confidence=min(f.confidence,.25)

        check_field(rec.study_design); check_field(rec.trial_registration)
        for s in rec.sample_sets:
            check_field(s.total_n)
            for a in s.arms:
                check_field(a.n); check_field(a.intervention)
            # Derived arm sum verifier
            if s.total_n and len(s.arms)>=2 and all(a.n for a in s.arms):
                arm_sum=sum(int(a.n.value) for a in s.arms)
                if s.total_n.status=="derived":
                    if int(s.total_n.value)==arm_sum:
                        s.total_n.confidence=max(s.total_n.confidence,.98)
                    else:
                        s.total_n.status="conflicting"
                elif int(s.total_n.value)!=arm_sum:
                    s.total_n.conflicts.append({"arm_sum":arm_sum})
                    s.total_n.status="conflicting"

        for r in rec.results:
            for f in [r.outcome,r.instrument,r.timepoint,r.n_intervention,r.n_comparator,
                      r.effect_measure,r.estimate,r.ci_lower,r.ci_upper,r.p_value,
                      r.significance,r.direction]:
                check_field(f)
            for f in r.group_values.values(): check_field(f)

        return rec
