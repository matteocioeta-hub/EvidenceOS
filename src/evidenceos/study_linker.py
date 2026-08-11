from __future__ import annotations
import re
from collections import defaultdict
from difflib import SequenceMatcher
from .models import CanonicalRecord, StudyReportLink
TRIAL_ID_PATTERNS=[r"\bNCT\d{8}\b",r"\bISRCTN\d+\b",r"\bACTRN\d{14}\b",r"\bChiCTR[-A-Za-z0-9]+\b",r"\bUMIN[-A-Za-z0-9]+\b"]
def _trial_ids(r):
    text=" ".join([r.title or "",r.abstract or ""]); found=set()
    for p in TRIAL_ID_PATTERNS: found.update(re.findall(p,text,re.I))
    return {x.upper() for x in found}
def _surname(a):
    parts=a.strip().split(); return parts[-1].lower() if parts else ""
def _title_core(t):
    t=re.sub(r"[^a-zA-Z0-9\s]"," ",(t or "")).lower()
    for ph in ["study protocol","protocol","secondary analysis","follow up","follow-up","randomized controlled trial","randomised controlled trial"]: t=t.replace(ph," ")
    return re.sub(r"\s+"," ",t).strip()
class StudyLinker:
    @classmethod
    def link(cls,records):
        links=[]; assigned=set(); c=1; m=defaultdict(list)
        for r in records:
            for tid in _trial_ids(r): m[tid].append(r)
        for tid,g in m.items():
            uniq=list({r.record_id:r for r in g}.values())
            if len(uniq)>=2:
                links.append(StudyReportLink(study_id=f"STUDY-{c:04d}",report_ids=[r.record_id for r in uniq],link_confidence=.99,link_method="deterministic",rationale=f"Shared trial registration identifier {tid}.")); c+=1; assigned.update(r.record_id for r in uniq)
        rem=[r for r in records if r.record_id not in assigned]; used=set()
        for i,a in enumerate(rem):
            if a.record_id in used: continue
            g=[a]
            for b in rem[i+1:]:
                if b.record_id in used: continue
                same=bool(a.authors and b.authors and _surname(a.authors[0])==_surname(b.authors[0])); yrs=(a.year is None or b.year is None or abs(a.year-b.year)<=3); sim=SequenceMatcher(None,_title_core(a.title),_title_core(b.title)).ratio()
                if same and yrs and sim>=.72: g.append(b); used.add(b.record_id)
            if len(g)>=2:
                links.append(StudyReportLink(study_id=f"STUDY-{c:04d}",report_ids=[r.record_id for r in g],link_confidence=.75,link_method="heuristic",rationale="Likely related reports based on first author, year proximity, and title similarity.")); c+=1; used.update(r.record_id for r in g)
        return links
