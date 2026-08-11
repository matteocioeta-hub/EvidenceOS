from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import settings
from .extraction_engine_v1 import ExtractionEngineV1
from .evidence_schema_v1 import UniversalEvidenceRecord
from .question_search import GuidedSearchRequest, GuidedSearchResponse, run_guided_search

app = FastAPI(
    title="EvidenceOS",
    version=__version__,
    description="Auditable scientific evidence extraction with provenance and consistency checks.",
)


class ExtractRequest(BaseModel):
    report_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=2000)
    text: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    record: UniversalEvidenceRecord


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/v1/extract", response_model=ExtractResponse)
def extract(request: ExtractRequest):
    if len(request.text) > settings.max_input_chars:
        raise HTTPException(status_code=413, detail="Input too large.")
    try:
        return ExtractResponse(
            record=ExtractionEngineV1().extract(
                request.report_id, request.title, request.text
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/research-search", response_model=GuidedSearchResponse)
def research_search(request: GuidedSearchRequest):
    try:
        return run_guided_search(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvidenceOS — Evidence you can inspect</title>
<meta name="description" content="EvidenceOS turns scientific reports into auditable evidence records with provenance, verification and epistemic checks.">
<style>
:root{
  --ink:#10221c; --muted:#607069; --line:#dce5e0; --soft:#f5f8f6;
  --brand:#173f35; --brand2:#285f50; --accent:#b8e4cc; --warn:#fff4d8;
  --danger:#ffe7e3; --white:#ffffff; --shadow:0 18px 50px rgba(16,34,28,.08);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:#fbfcfb;line-height:1.5}
a{color:inherit;text-decoration:none}.wrap{max-width:1180px;margin:auto;padding:0 24px}
nav{height:72px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(220,229,224,.8);background:rgba(251,252,251,.93);backdrop-filter:blur(12px);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:12px;font-weight:750;letter-spacing:-.03em;font-size:20px}.mark{width:32px;height:32px;border-radius:10px;background:var(--brand);display:grid;place-items:center;color:white;font-size:14px}.alpha{font-size:11px;background:#e9f1ed;color:var(--brand);padding:4px 8px;border-radius:999px;font-weight:700;letter-spacing:.04em}
.navlinks{display:flex;gap:24px;color:var(--muted);font-size:14px}.hero{padding:82px 0 56px}.eyebrow{display:inline-flex;gap:8px;align-items:center;padding:7px 11px;border:1px solid var(--line);border-radius:999px;background:white;color:var(--brand2);font-size:13px;font-weight:650}.dot{width:7px;height:7px;background:#44a477;border-radius:50%}
h1{font-size:clamp(46px,7vw,78px);line-height:.98;letter-spacing:-.06em;max-width:940px;margin:24px 0}.lede{max-width:720px;font-size:20px;color:var(--muted);margin:0 0 32px}.hero-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:28px;align-items:end}.hero-card{border:1px solid var(--line);background:white;border-radius:24px;padding:26px;box-shadow:var(--shadow)}
.kicker{font-size:12px;text-transform:uppercase;letter-spacing:.13em;font-weight:800;color:var(--brand2)}.metric{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}.metric div{background:var(--soft);border-radius:16px;padding:15px}.metric b{display:block;font-size:20px}.metric span{font-size:12px;color:var(--muted)}
section{padding:52px 0}.section-title{font-size:34px;letter-spacing:-.04em;margin:0 0 10px}.section-sub{color:var(--muted);max-width:720px;margin:0 0 28px}.workspace{display:grid;grid-template-columns:390px 1fr;gap:22px;align-items:start}.panel{background:white;border:1px solid var(--line);border-radius:22px;box-shadow:0 10px 30px rgba(16,34,28,.045)}.form{padding:22px;position:sticky;top:94px}.panel h3{margin:0 0 4px;letter-spacing:-.02em}.muted{color:var(--muted);font-size:13px}.field{margin-top:18px}label{display:block;font-size:12px;font-weight:750;margin-bottom:7px;text-transform:uppercase;letter-spacing:.06em;color:#4c5e57}input,textarea{width:100%;border:1px solid var(--line);border-radius:13px;padding:12px 13px;font:inherit;color:var(--ink);background:#fdfefd;outline:none}input:focus,textarea:focus{border-color:#84ad9d;box-shadow:0 0 0 3px rgba(132,173,157,.12)}textarea{min-height:250px;resize:vertical;font-size:13px;line-height:1.45}.actions{display:flex;gap:9px;margin-top:14px}button{border:0;border-radius:12px;padding:12px 15px;font-weight:750;cursor:pointer;font:inherit}.primary{background:var(--brand);color:white;flex:1}.secondary{background:#edf3ef;color:var(--brand)}button:disabled{opacity:.55;cursor:wait}
.results{padding:22px;min-height:560px}.empty{height:500px;display:grid;place-items:center;text-align:center;color:var(--muted)}.empty-icon{width:58px;height:58px;border-radius:18px;background:#edf4f0;margin:0 auto 13px;display:grid;place-items:center;color:var(--brand);font-size:22px}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}.stat{background:var(--soft);padding:14px;border-radius:14px}.stat strong{display:block;font-size:19px}.stat small{color:var(--muted)}.status{display:inline-flex;padding:5px 8px;border-radius:8px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}.verified{background:#dff5e8;color:#236846}.derived{background:#e7eef8;color:#35557f}.warning{background:var(--warn);color:#755411}.critical{background:var(--danger);color:#8c3529}.unverified,.ambiguous,.conflicting{background:#f0eceb;color:#6e4b45}
.block{border-top:1px solid var(--line);padding:18px 0}.block:first-of-type{border-top:0}.block-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.block h4{margin:0;font-size:15px}.record{margin-top:10px;padding:13px;background:#fafcfb;border:1px solid #e5ece8;border-radius:14px;font-size:13px}.row{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:5px 0}.row span:first-child{color:var(--muted)}.alarm{padding:12px 13px;border-radius:13px;margin-top:8px;font-size:13px}.alarm.warning{border:1px solid #f0dfa9}.alarm.critical{border:1px solid #efc0b9}.alarm.info{background:#edf3f7;color:#416174}
.modules{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.module{padding:20px;border:1px solid var(--line);border-radius:18px;background:white}.module h3{margin:8px 0 6px;font-size:16px}.module p{margin:0;color:var(--muted);font-size:13px}.module .state{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:var(--brand2)}.foot{margin-top:36px;padding:28px 0 44px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px}.spinner{width:17px;height:17px;border:2px solid #ffffff55;border-top-color:#fff;border-radius:50%;display:inline-block;animation:spin .7s linear infinite;vertical-align:-3px;margin-right:7px}@keyframes spin{to{transform:rotate(360deg)}}

.searchbox{background:linear-gradient(145deg,#173f35,#224f43);color:white;border-radius:26px;padding:26px;box-shadow:var(--shadow)}
.searchbox .field label{color:#d6e6df}.searchbox input{background:rgba(255,255,255,.98)}
.searchgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.searchwide{grid-column:1/-1}
.search-results{margin-top:22px}.record-list{display:grid;gap:10px}.paper{border:1px solid var(--line);background:white;border-radius:16px;padding:16px}
.paper-title{font-weight:750;line-height:1.3}.paper-meta{color:var(--muted);font-size:12px;margin-top:5px}.paper-abstract{font-size:13px;color:#41534c;margin-top:8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.db{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;background:#eaf2ee;color:#315e50;padding:4px 7px;border-radius:7px;margin-right:5px}
.pico{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:14px 0}.pico div{padding:11px;background:#f4f8f6;border-radius:12px}.pico b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--brand2);margin-bottom:4px}.pico span{font-size:12px}


.intel-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0 18px}
.intel-card{padding:12px;border-radius:13px;border:1px solid var(--line);background:#fafcfb}
.intel-card b{font-size:20px;display:block}.intel-card span{font-size:11px;color:var(--muted)}
.paper-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.elig{font-size:10px;padding:4px 7px;border-radius:7px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.elig.include{background:#dff5e8;color:#236846}.elig.indirect{background:#fff1cc;color:#745512}.elig.uncertain{background:#edf0f2;color:#4c5b63}.elig.exclude{background:#f4e8e5;color:#7c443b}
.design{font-size:11px;color:var(--brand2);font-weight:700;margin-top:5px}
.filterbar{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 14px}.filterbar button{padding:7px 10px;font-size:11px;background:#edf3ef;color:var(--brand)}.filterbar button.active{background:var(--brand);color:white}
.linkbox{background:#f7faf8;border:1px dashed #cfdcd5;padding:12px;border-radius:12px;margin-top:10px;font-size:12px}

.scope-options{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.scope-option{display:block;cursor:pointer}
.scope-option input{position:absolute;opacity:0;pointer-events:none}
.scope-card{display:block;padding:12px;border:1px solid rgba(255,255,255,.24);border-radius:12px;background:rgba(255,255,255,.08);transition:.15s}
.scope-card b{display:block;color:white;font-size:13px}.scope-card span{display:block;color:#d6e6df;font-size:11px;margin-top:3px}
.scope-option input:checked + .scope-card{background:white;border-color:white;box-shadow:0 5px 16px rgba(0,0,0,.12)}
.scope-option input:checked + .scope-card b{color:var(--brand)}.scope-option input:checked + .scope-card span{color:var(--muted)}
.scope-note{font-size:11px;color:#d6e6df;margin-top:8px;line-height:1.4}
@media(max-width:900px){.hero-grid,.workspace{grid-template-columns:1fr}.searchgrid{grid-template-columns:1fr}.searchwide{grid-column:auto}.pico{grid-template-columns:1fr 1fr}.form{position:static}.modules{grid-template-columns:1fr 1fr}.summary{grid-template-columns:1fr 1fr}.navlinks{display:none}}@media(max-width:560px){.scope-options{grid-template-columns:1fr}.wrap{padding:0 16px}.hero{padding-top:48px}.modules{grid-template-columns:1fr}.summary{grid-template-columns:1fr 1fr}.metric{grid-template-columns:1fr}.foot{flex-direction:column}}
</style>
</head>
<body>
<nav><div class="wrap" style="width:100%;display:flex;align-items:center;justify-content:space-between"><a class="brand" href="#"><span class="mark">E</span>EvidenceOS <span class="alpha">ALPHA</span></a><div class="navlinks"><a href="#ask">Ask EvidenceOS</a><a href="#workspace">Analyse a study</a><a href="#modules">Platform</a><a href="/docs">API docs</a></div></div></nav>
<main>
<section class="hero"><div class="wrap"><span class="eyebrow"><span class="dot"></span> Auditable evidence intelligence</span><h1>Evidence you can inspect,<br>not just summaries you can read.</h1><div class="hero-grid"><div><p class="lede">EvidenceOS reconstructs the path from scientific reports to structured evidence, preserving provenance and surfacing contradictions before they become conclusions.</p><a href="#workspace"><button class="primary" style="padding:14px 18px">Analyse a study →</button></a></div><div class="hero-card"><div class="kicker">Current public alpha</div><div class="metric"><div><b>Source-linked</b><span>Every direct field carries provenance</span></div><div><b>Field-level</b><span>Verified, derived or unresolved</span></div><div><b>Adversarial</b><span>Consistency alarms challenge outputs</span></div></div></div></div></div></section>


<section id="ask"><div class="wrap">
<div class="kicker">Question-first evidence discovery</div>
<h2 class="section-title">Ask EvidenceOS.</h2>
<p class="section-sub">Define the clinical or research question you actually want answered. In this public alpha, you confirm the PICO explicitly so the search logic remains transparent and reproducible.</p>
<div class="searchbox">
  <div class="searchgrid">
    <div class="field searchwide"><label>Research question</label><input id="qtext" placeholder="e.g. Does exercise improve pain and fatigue in adults with fibromyalgia?"></div>
    <div class="field"><label>Population</label><input id="qpop" placeholder="Adults with fibromyalgia"></div>
    <div class="field"><label>Intervention</label><input id="qint" placeholder="Therapeutic exercise"></div>
    <div class="field"><label>Comparator</label><input id="qcomp" placeholder="Usual care / active comparator / leave blank"></div>
    <div class="field"><label>Outcomes</label><input id="qout" placeholder="Pain, fatigue, quality of life"></div>
    <div class="field"><label>Timepoint</label><input id="qtime" placeholder="12 weeks / long term / leave blank"></div>
    <div class="field searchwide"><label>Search scope</label>
      <div class="scope-options">
        <label class="scope-option"><input type="radio" name="qscope" value="10"><span class="scope-card"><b>Quick</b><span>Up to 10 records · rapid exploration</span></span></label>
        <label class="scope-option"><input type="radio" name="qscope" value="25" checked><span class="scope-card"><b>Standard</b><span>Up to 25 records · recommended</span></span></label>
        <label class="scope-option"><input type="radio" name="qscope" value="50"><span class="scope-card"><b>Broad</b><span>Up to 50 records · wider exploration</span></span></label>
      </div>
      <div class="scope-note">Controls how many PubMed records EvidenceOS initially examines. It does not represent evidence quality or certainty.</div>
    </div>
  </div>
  <div class="actions"><button class="secondary" onclick="questionDemo()">Load example</button><button id="searchBtn" class="primary" onclick="searchEvidence()">Search PubMed</button></div>
  <div id="searchErr" style="margin-top:12px;color:#ffd7cf;font-size:13px"></div>
</div>
<div id="searchResults" class="search-results"></div>
</div></section>

<section id="workspace"><div class="wrap"><div class="kicker">Live workspace</div><h2 class="section-title">Turn a report into an auditable evidence record.</h2><p class="section-sub">Paste scientific report text. EvidenceOS will extract what it can support, reconstruct sample structure, map results and flag inconsistencies. The alpha intentionally leaves unsupported fields unresolved.</p><div class="workspace"><div class="panel form"><h3>Study input</h3><div class="muted">Plain-text report extraction</div><div class="field"><label>Report ID</label><input id="rid" value="RCT-001"></div><div class="field"><label>Study title</label><input id="ttl" placeholder="Paste the study title"></div><div class="field"><label>Report text</label><textarea id="txt" placeholder="Paste Methods, Results, tables converted to text, or the relevant full-text sections..."></textarea></div><div class="actions"><button class="secondary" onclick="demo()">Load demo</button><button id="runBtn" class="primary" onclick="run()">Extract evidence</button></div><div id="err" class="muted" style="margin-top:12px;color:#913f34"></div></div><div class="panel results" id="results"><div class="empty"><div><div class="empty-icon">⌁</div><strong>Your evidence record will appear here.</strong><div class="muted" style="max-width:370px;margin:7px auto">EvidenceOS separates what is reported, what is derived and what remains uncertain.</div></div></div></div></div></div></section>

<section id="modules"><div class="wrap"><div class="kicker">Evidence intelligence platform</div><h2 class="section-title">Beyond extraction.</h2><p class="section-sub">The broader EvidenceOS architecture is being validated as separate modules rather than presented as one opaque AI answer.</p><div class="modules"><div class="module"><span class="state">Live alpha</span><h3>Structured Extraction</h3><p>Sample flow, arms, outcomes, timepoints, effect estimates and provenance.</p></div><div class="module"><span class="state">Experimental</span><h3>Critical Appraisal</h3><p>Outcome-specific methodological signals and RoB 2 assistance with source-linked rationale.</p></div><div class="module"><span class="state">Experimental</span><h3>Body of Evidence</h3><p>Groups compatible results into claims without collapsing studies, outcomes or timepoints.</p></div><div class="module"><span class="state">Experimental</span><h3>Challenge Engine</h3><p>Actively looks for comparator traps, contradictory results and quality asymmetries.</p></div><div class="module"><span class="state">Experimental</span><h3>Gap Falsification</h3><p>Searches for literature that could disprove an apparent research gap before calling it novel.</p></div><div class="module"><span class="state">In validation</span><h3>Certainty Calibration</h3><p>Separates effect magnitude from how confidently the evidence supports a conclusion.</p></div></div><div class="foot"><div>EvidenceOS v""" + __version__ + r""" · Research software alpha</div><div>Not a substitute for independent methodological or clinical judgement.</div></div></div></section>
</main>

<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function badge(status){const s=status||'unverified';return `<span class="status ${esc(s)}">${esc(s)}</span>`}
function fieldRow(label,f){if(!f)return '';let val=f.value;if(typeof val==='object')val=JSON.stringify(val);return `<div class="row"><span>${esc(label)}</span><div><b>${esc(val)}</b> ${f.unit?`<span class="muted">${esc(f.unit)}</span>`:''} ${badge(f.status)}${f.derivation?`<div class="muted">Derived: ${esc(f.derivation)}</div>`:''}</div></div>`}
function render(rec){
 const samples=rec.sample_sets||[], results=rec.results||[], alarms=rec.alarms||[];
 const grounded=samples.filter(s=>s.total_n&&['verified','derived'].includes(s.total_n.status)).length;
 const html=[];
 html.push(`<div class="block-head"><div><div class="kicker">Universal Evidence Record</div><h3 style="font-size:24px;margin:3px 0 0">${esc(rec.title)}</h3><div class="muted">${esc(rec.report_id)}</div></div>${badge(rec.study_design?.status||'unverified')}</div>`);
 html.push(`<div class="summary"><div class="stat"><strong>${samples.length}</strong><small>Sample sets</small></div><div class="stat"><strong>${results.length}</strong><small>Results mapped</small></div><div class="stat"><strong>${alarms.length}</strong><small>Consistency alarms</small></div><div class="stat"><strong>${grounded}</strong><small>Grounded sample fields</small></div></div>`);
 html.push(`<div class="block"><h4>Study identity</h4><div class="record">${fieldRow('Design',rec.study_design)}${fieldRow('Trial registration',rec.trial_registration)}</div></div>`);
 html.push(`<div class="block"><h4>Sample structure</h4>${samples.length?samples.map(s=>`<div class="record"><div class="block-head"><b>${esc(s.role)}</b>${s.total_n?badge(s.total_n.status):''}</div>${fieldRow('Total N',s.total_n)}${(s.arms||[]).map(a=>`<div class="row"><span>${esc(a.label)}</span><div>${a.n?`<b>n=${esc(a.n.value)}</b> ${badge(a.n.status)}`:''}</div></div>`).join('')}</div>`).join(''):'<div class="record muted">No sample structure could be verified.</div>'}</div>`);
 html.push(`<div class="block"><h4>Outcome results</h4>${results.length?results.map(r=>`<div class="record"><div class="block-head"><b>${esc(r.outcome?.value||'Outcome')}</b>${r.direction?badge(r.direction.status):''}</div>${fieldRow('Instrument',r.instrument)}${fieldRow('Timepoint',r.timepoint)}${fieldRow('Effect measure',r.effect_measure)}${fieldRow('Estimate',r.estimate)}${fieldRow('95% CI lower',r.ci_lower)}${fieldRow('95% CI upper',r.ci_upper)}${fieldRow('p value',r.p_value)}${fieldRow('Direction',r.direction)}</div>`).join(''):'<div class="record muted">No result format was confidently mapped. Unsupported formats remain unresolved rather than guessed.</div>'}</div>`);
 html.push(`<div class="block"><h4>Epistemic alarms</h4>${alarms.length?alarms.map(a=>`<div class="alarm ${esc(a.severity)}"><b>${esc(a.code)}</b><div>${esc(a.message)}</div></div>`).join(''):'<div class="record muted">No internal consistency alarm was triggered for the extracted fields.</div>'}</div>`);
 html.push(`<div class="block"><details><summary style="cursor:pointer;font-weight:700">Raw record JSON</summary><pre style="white-space:pre-wrap;font-size:11px;background:#f7f9f8;padding:14px;border-radius:12px;overflow:auto">${esc(JSON.stringify(rec,null,2))}</pre></details></div>`);
 document.getElementById('results').innerHTML=html.join('');
}

function questionDemo(){
 qtext.value='Does exercise improve pain and fatigue in adults with fibromyalgia?';
 qpop.value='Adults with fibromyalgia';qint.value='Therapeutic exercise';
 qcomp.value='Usual care';qout.value='Pain, fatigue';qtime.value='12 weeks';
 document.querySelector('input[name="qscope"][value="25"]').checked=true;
}
function renderSearch(data){
 const q=data.structured_question, r=data.retrieval||{}, intel=data.study_intelligence||{};
 const items=intel.study_intelligence||[], strategies=r.strategies||[], links=intel.study_links||[];
 window._eosIntel=items;
 const root=document.getElementById('searchResults');
 const pico=`<div class="pico"><div><b>Population</b><span>${esc(q.population?.label)}</span></div><div><b>Intervention</b><span>${esc(q.intervention?.label)}</span></div><div><b>Comparator</b><span>${esc(q.comparator?.label)}</span></div><div><b>Outcomes</b><span>${esc((q.outcomes||[]).map(x=>x.label).join(', '))}</span></div></div>`;
 const filters=`<div class="filterbar"><button class="active" onclick="filterPapers('all',this)">All</button><button onclick="filterPapers('include',this)">Likely relevant</button><button onclick="filterPapers('indirect',this)">Indirect</button><button onclick="filterPapers('uncertain',this)">Uncertain</button><button onclick="filterPapers('exclude',this)">Excluded</button></div>`;
 root.innerHTML=`<div class="panel" style="padding:22px"><div class="block-head"><div><div class="kicker">Evidence Map + Study Intelligence</div><h3 style="font-size:24px;margin:3px 0">${esc(q.original_text)}</h3></div><span class="status verified">live retrieval</span></div>${pico}<div class="summary"><div class="stat"><strong>${r.records_before_deduplication??0}</strong><small>Records retrieved</small></div><div class="stat"><strong>${r.records_after_deduplication??0}</strong><small>Unique records</small></div><div class="stat"><strong>${strategies.length}</strong><small>Search strategies</small></div><div class="stat"><strong>${links.length}</strong><small>Report links detected</small></div></div><div class="intel-summary"><div class="intel-card"><b>${intel.likely_include??0}</b><span>Likely relevant</span></div><div class="intel-card"><b>${intel.indirect??0}</b><span>Indirect</span></div><div class="intel-card"><b>${intel.uncertain??0}</b><span>Uncertain</span></div><div class="intel-card"><b>${intel.excluded??0}</b><span>Excluded</span></div></div><div class="record" style="margin-bottom:14px"><b>Interpretation boundary</b><div class="muted">Eligibility and design labels are machine-assisted screening signals, not final systematic-review inclusion decisions. Full-text verification remains required.</div></div>${filters}<div id="paperList" class="record-list"></div>${links.length?`<div class="linkbox"><b>Potential multiple-report links</b><div>${links.map(l=>`${esc(l.study_id)}: ${esc((l.report_ids||[]).join(', '))}`).join('<br>')}</div></div>`:''}<details style="margin-top:14px"><summary style="cursor:pointer;font-weight:700">Search strategies</summary><pre style="white-space:pre-wrap;font-size:11px;background:#f7f9f8;padding:14px;border-radius:12px">${esc(JSON.stringify(strategies,null,2))}</pre></details></div>`;
 renderPaperList(items,'all');
}
function renderPaperList(items,filter){
 const list=document.getElementById('paperList'); if(!list)return;
 const filtered=filter==='all'?items:items.filter(x=>x.eligibility?.overall===filter);
 list.innerHTML=filtered.slice(0,40).map(x=>{
   const p=x.record||{}, e=x.eligibility||{}, d=x.design||{};
   const db=(p.source_databases||[]).map(s=>`<span class="db">${esc(s)}</span>`).join('');
   const ident=[p.year,p.journal,p.pmid?`PMID ${p.pmid}`:'',p.doi?`DOI ${p.doi}`:''].filter(Boolean).join(' · ');
   return `<div class="paper" data-elig="${esc(e.overall)}"><div class="paper-head"><div style="min-width:0"><div>${db}</div><div class="paper-title">${esc(p.title)}</div></div><span class="elig ${esc(e.overall)}">${esc(e.overall||'uncertain')}</span></div><div class="design">${esc(d.final_label||'uncertain design')} · confidence ${Math.round((d.confidence||0)*100)}%</div><div class="paper-meta">${esc(ident)}</div>${p.abstract?`<div class="paper-abstract">${esc(p.abstract)}</div>`:''}<details style="margin-top:8px"><summary class="muted" style="cursor:pointer">Why this classification?</summary><div class="muted" style="margin-top:6px">${esc(e.exclusion_reason||((e.dimensions||[]).map(y=>`${y.dimension}: ${y.judgement}`).join(' · '))||'No rationale available.')}</div></details></div>`;
 }).join('')||'<div class="record muted">No records in this category.</div>';
}
function filterPapers(filter,btn){
 document.querySelectorAll('.filterbar button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
 renderPaperList(window._eosIntel||[],filter);
}
async function searchEvidence(){
 const btn=document.getElementById('searchBtn'),err=document.getElementById('searchErr');err.textContent='';
 const outs=qout.value.split(',').map(x=>x.trim()).filter(Boolean);
 if(!qtext.value.trim()||!qpop.value.trim()||!qint.value.trim()||!outs.length){err.textContent='Question, population, intervention and at least one outcome are required.';return}
 btn.disabled=true;btn.innerHTML='<span class="spinner"></span>Searching';
 try{
   const response=await fetch('/v1/research-search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     question:qtext.value,population:qpop.value,intervention:qint.value,comparator:qcomp.value,
     outcomes:outs,timepoint:qtime.value,max_results_per_strategy:Number(document.querySelector('input[name="qscope"]:checked')?.value||25)
   })});
   const raw=await response.text();
   let data=null;
   const ct=(response.headers.get('content-type')||'').toLowerCase();
   if(ct.includes('application/json')){
     try{data=JSON.parse(raw)}catch(_){data=null}
   }
   if(!response.ok){
     if(data&&data.detail) throw new Error(data.detail);
     if(raw.trim().startsWith('<')){
       throw new Error(`EvidenceOS backend returned an HTML error page (HTTP ${response.status}). Check the latest Render deploy/logs; the search request may have timed out.`);
     }
     throw new Error(raw.slice(0,300)||`Search failed (HTTP ${response.status})`);
   }
   if(!data){
     throw new Error('EvidenceOS received a non-JSON response from the backend.');
   }
   renderSearch(data);
 }catch(e){err.textContent=e.message}
 finally{btn.disabled=false;btn.textContent='Search PubMed'}
}

async function run(){
 const btn=document.getElementById('runBtn'),err=document.getElementById('err');err.textContent='';
 if(!ttl.value.trim()||!txt.value.trim()){err.textContent='Add a study title and report text.';return}
 btn.disabled=true;btn.innerHTML='<span class="spinner"></span>Extracting';
 try{
   const r=await fetch('/v1/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({report_id:rid.value,title:ttl.value,text:txt.value})});
   const j=await r.json();
   if(!r.ok)throw new Error(j.detail||'Extraction failed');
   render(j.record);
 }catch(e){err.textContent=e.message}
 finally{btn.disabled=false;btn.textContent='Extract evidence'}
}
function demo(){
 ttl.value='High-intensity versus moderate-intensity exercise for chronic low back pain';
 rid.value='DEMO-RCT-001';
 txt.value=`Participants with chronic nonspecific low back pain were randomly assigned to an experimental high intensity training group (HIT) or a moderate intensity training control group (MIT).

Thirty-eight participants were included in the initial PRE-POST analysis, HIT n = 19 and MIT n = 19. Finally, 29 participants were included in the follow-up analysis, HIT n = 16 and MIT n = 13.

Disability, MODI %:
HIT PRE 20.9 (8.7), POST 7.5 (5.4), FU 7.9 (8.4).
MIT PRE 16.2 (8.2), POST 10.6 (3.0), FU 10.4 (9.6).
Difference of deltas PRE to FU between HIT and MIT: 3.6, significant in favour of HIT.

Pain intensity, NPRS 0-10:
HIT PRE 5.6 (1.5), POST 2.6 (1.3), FU 2.3 (2.1).
MIT PRE 5.0 (1.7), POST 3.5 (1.7), FU 2.3 (1.1).
Difference of deltas PRE to FU between HIT and MIT: 0.5, not significant.`;
}
</script>
</body>
</html>""")
