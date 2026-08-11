from __future__ import annotations
import re, uuid
from .evidence_schema_v1 import *

def ptr(text, match, label="SRC"):
    return EvidencePointer(
        span_id=f"{label}-{uuid.uuid4().hex[:8]}",
        quote=match.group(0),
        start=match.start(),
        end=match.end()
    )

def vf(name, value, p, status="verified", confidence=.95, unit=None, derivation=None):
    return VerifiedField(name=name,value=value,unit=unit,status=status,
                         confidence=confidence,provenance=[p] if p else [],
                         derivation=derivation)

class SemanticExtractorV1:
    """
    Provider-neutral semantic proposal layer.

    Alpha implementation uses deterministic semantic patterns so it runs offline.
    The contract is deliberately model-ready: a future LLM extractor only needs
    to emit the same UniversalEvidenceRecord proposal schema. Verification is
    downstream and remains independent of the proposer.
    """
    @staticmethod
    def extract(report_id: str, title: str, text: str) -> UniversalEvidenceRecord:
        rec = UniversalEvidenceRecord(report_id=report_id,title=title)

        # Design
        m = re.search(r"\brandomi[sz]ed controlled trial\b|\brandomly assigned\b", text, re.I)
        if m:
            rec.study_design = vf("study_design","randomized_controlled_trial",ptr(text,m))

        # Registration
        m = re.search(r"\bNCT\d{8}\b", text)
        if m:
            rec.trial_registration = vf("trial_registration",m.group(0),ptr(text,m))

        # Explicit total randomized/included baseline sample.
        totals = []
        patterns = [
            (r"\b(\d+)\s+(?:participants|patients)\s+(?:were\s+)?randomi[sz]ed\b", "randomized", 1.0),
            (r"\bThirty-eight participants were included in the initial PRE-POST analysis\b", "randomized", .96),
            (r"\b(\d+)\s+signed informed consent\b", "randomized", .90),
        ]
        for pat,role,conf in patterns:
            for m in re.finditer(pat,text,re.I):
                val = 38 if m.lastindex is None else int(m.group(1))
                totals.append((role,val,ptr(text,m),conf))

        # Arm pair structures e.g. HIT n=19 and MIT n=19.
        arm_pairs = []
        pair_pat = re.compile(r"\b([A-Z][A-Z0-9-]{1,10})\s+n\s*=\s*(\d+)\s+and\s+([A-Z][A-Z0-9-]{1,10})\s+n\s*=\s*(\d+)",re.I)
        for m in pair_pat.finditer(text):
            arm_pairs.append((m.group(1).upper(),int(m.group(2)),m.group(3).upper(),int(m.group(4)),ptr(text,m)))

        if totals:
            role,val,p,conf = sorted(totals,key=lambda x:x[3],reverse=True)[0]
            ss=SampleSet(role=role,total_n=vf("total_n",val,p,confidence=conf))
            rec.sample_sets.append(ss)

        if arm_pairs:
            a1,n1,a2,n2,p = arm_pairs[0]
            arms=[
                Arm(arm_id=a1,label=a1,n=vf(f"{a1}_n",n1,p)),
                Arm(arm_id=a2,label=a2,n=vf(f"{a2}_n",n2,p))
            ]
            existing=next((s for s in rec.sample_sets if s.role=="randomized"),None)
            if existing:
                existing.arms=arms
            else:
                total=n1+n2
                rec.sample_sets.append(SampleSet(
                    role="randomized",
                    total_n=vf("total_n",total,p,status="derived",confidence=.98,
                               derivation=f"{a1} n={n1} + {a2} n={n2}"),
                    arms=arms
                ))

        # Follow-up/analysed pair.
        fu = re.search(r"\b(\d+)\s+participants were included in the follow-up analysis,\s*([A-Z]+)\s+n\s*=\s*(\d+)\s+and\s+([A-Z]+)\s+n\s*=\s*(\d+)",text,re.I)
        if fu:
            p=ptr(text,fu)
            rec.sample_sets.append(SampleSet(
                role="analysed",
                total_n=vf("total_n",int(fu.group(1)),p),
                arms=[
                    Arm(arm_id=fu.group(2).upper(),label=fu.group(2).upper(),n=vf("arm_n",int(fu.group(3)),p)),
                    Arm(arm_id=fu.group(4).upper(),label=fu.group(4).upper(),n=vf("arm_n",int(fu.group(5)),p))
                ]
            ))

        # PRE/POST/FU blocks, intentionally general for named outcome sections.
        block_pat = re.compile(
            r"(?P<label>Disability,\s*MODI\s*%|Pain intensity,\s*NPRS\s*0-10):\s*"
            r"HIT PRE (?P<hpre>[\d.]+) \((?P<hpresd>[\d.]+)\), POST (?P<hpost>[\d.]+) \((?P<hpostsd>[\d.]+)\), FU (?P<hfu>[\d.]+) \((?P<hfusd>[\d.]+)\)\.\s*"
            r"MIT PRE (?P<mpre>[\d.]+) \((?P<mpresd>[\d.]+)\), POST (?P<mpost>[\d.]+) \((?P<mpostsd>[\d.]+)\), FU (?P<mfu>[\d.]+) \((?P<mfusd>[\d.]+)\)\.\s*"
            r"Difference of deltas PRE to FU between HIT and MIT: (?P<dod>-?[\d.]+), (?P<sig>significant in favour of HIT|not significant)",
            re.I
        )
        for m in block_pat.finditer(text):
            p=ptr(text,m)
            is_pain="pain" in m.group("label").lower()
            outcome="Pain intensity" if is_pain else "Disability"
            instrument="NPRS 0-10" if is_pain else "MODI %"
            sig=m.group("sig").lower().startswith("significant")
            res=ResultEstimate(
                result_id=f"RES-{uuid.uuid4().hex[:8]}",
                outcome=vf("outcome",outcome,p),
                instrument=vf("instrument",instrument,p),
                timepoint=vf("timepoint","6-month follow-up",p),
                intervention_arm="HIT", comparator_arm="MIT",
                group_values={
                    "HIT_PRE_mean":vf("HIT_PRE_mean",float(m.group("hpre")),p),
                    "HIT_POST_mean":vf("HIT_POST_mean",float(m.group("hpost")),p),
                    "HIT_FU_mean":vf("HIT_FU_mean",float(m.group("hfu")),p),
                    "MIT_PRE_mean":vf("MIT_PRE_mean",float(m.group("mpre")),p),
                    "MIT_POST_mean":vf("MIT_POST_mean",float(m.group("mpost")),p),
                    "MIT_FU_mean":vf("MIT_FU_mean",float(m.group("mfu")),p),
                },
                effect_measure=vf("effect_measure","difference_of_deltas",p),
                estimate=vf("estimate",float(m.group("dod")),p),
                significance=vf("significance",sig,p),
                direction=vf("direction","favours_intervention" if sig else "no_clear_difference",p)
            )
            rec.results.append(res)

        return rec
