from __future__ import annotations
import uuid
from .evidence_schema_v1 import *

def alarm(severity,code,message,fields=None):
    return EvidenceAlarm(alarm_id=f"ALM-{uuid.uuid4().hex[:8]}",severity=severity,
                         code=code,message=message,related_fields=fields or [])

class ConsistencyEngineV1:
    @staticmethod
    def run(rec: UniversalEvidenceRecord) -> UniversalEvidenceRecord:
        alarms=[]

        # Arm-count integrity
        for s in rec.sample_sets:
            if s.total_n and len(s.arms)>=2 and all(a.n for a in s.arms):
                arm_sum=sum(int(a.n.value) for a in s.arms)
                if int(s.total_n.value)!=arm_sum:
                    alarms.append(alarm("critical","ARM_TOTAL_MISMATCH",
                        f"{s.role} total n={s.total_n.value}, but arm counts sum to {arm_sum}.",
                        ["sample_sets"]))

        # Randomized vs analysed distinction
        rnd=next((s for s in rec.sample_sets if s.role=="randomized"),None)
        ana=next((s for s in rec.sample_sets if s.role=="analysed"),None)
        if rnd and ana and rnd.total_n and ana.total_n:
            if int(ana.total_n.value) < int(rnd.total_n.value):
                alarms.append(alarm("warning","ATTRITION_PRESENT",
                    f"Randomized n={rnd.total_n.value}; analysed n={ana.total_n.value}. Do not collapse these denominators.",
                    ["randomized.total_n","analysed.total_n"]))

        # Statistical coherence
        for r in rec.results:
            if r.ci_lower and r.ci_upper and r.significance:
                crosses=float(r.ci_lower.value)<=0<=float(r.ci_upper.value)
                if crosses and r.significance.value is True:
                    alarms.append(alarm("critical","CI_SIGNIFICANCE_CONFLICT",
                        f"{r.result_id}: CI crosses null but result marked significant.",[r.result_id]))
            if r.p_value and r.significance:
                p=float(r.p_value.value)
                if p>.05 and r.significance.value is True:
                    alarms.append(alarm("critical","P_SIGNIFICANCE_CONFLICT",
                        f"{r.result_id}: p={p} but result marked significant.",[r.result_id]))
            if r.significance and r.direction:
                if r.significance.value is False and r.direction.value not in ("no_clear_difference","uncertain"):
                    alarms.append(alarm("critical","DIRECTION_SIGNIFICANCE_CONFLICT",
                        f"{r.result_id}: non-significant result represented as directional superiority.",[r.result_id]))

        rec.alarms=alarms
        return rec
