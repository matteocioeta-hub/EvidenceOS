from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import settings
from .extraction_engine_v1 import ExtractionEngineV1
from .evidence_schema_v1 import UniversalEvidenceRecord
from .question_search import GuidedSearchRequest, GuidedSearchResponse, run_guided_search
from .study_workspace import StudyWorkspaceRequest, StudyWorkspaceResponse, build_study_workspace
from .pdf_ingest import extract_pdf_text, PdfIngestError
from .universal_trust_engine import UniversalTrustAssessment, assess_full_text
from .evidence_workspace import SynthesisRequest, SynthesisResponse, synthesize
from .gap_falsification_live import GapFalsificationRequest, GapFalsificationResponse, falsify_gap
from .conclusion_challenge_live import ConclusionChallengeRequest, ConclusionChallengeResponse, challenge_conclusion
from .candidate_intake import CandidateIntakeRequest, CandidateIntakeResponse, intake_candidate

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


class PdfExtractResponse(BaseModel):
    record: UniversalEvidenceRecord
    filename: str
    pages: int
    extracted_characters: int
    trust_assessment: UniversalTrustAssessment


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


@app.post("/v1/extract-pdf", response_model=PdfExtractResponse)
async def extract_pdf(
    report_id: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
):
    filename = file.filename or "full_text.pdf"

    if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    try:
        data = await file.read()
        text, pages = extract_pdf_text(data)
        if len(text) > settings.max_input_chars:
            raise HTTPException(
                status_code=413,
                detail=f"Extracted PDF text exceeds EVIDENCEOS_MAX_INPUT_CHARS={settings.max_input_chars}.",
            )
        record = ExtractionEngineV1().extract(report_id, title, text)
        try:
            trust = assess_full_text(report_id, title, text)
        except Exception as appraisal_exc:
            trust = UniversalTrustAssessment(
                design="other",
                framework="Appraisal unavailable",
                status="appraisal_error",
                headline="Full-text extraction succeeded; appraisal was not completed",
                explanation=(
                    "EvidenceOS extracted the PDF successfully, but the methodological "
                    "appraisal layer encountered an internal error. The evidence record "
                    "is still available and no trust judgement has been invented."
                ),
                overall_judgement="unresolved",
                limitations=[str(appraisal_exc)[:300]],
            )
        return PdfExtractResponse(
            record=record,
            filename=filename,
            pages=pages,
            extracted_characters=len(text),
            trust_assessment=trust,
        )
    except PdfIngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/v1/synthesize", response_model=SynthesisResponse)
def synthesize_evidence(request: SynthesisRequest):
    try:
        return synthesize(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/falsify-gap", response_model=GapFalsificationResponse)
def falsify_gap_endpoint(request: GapFalsificationRequest):
    try:
        return falsify_gap(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/challenge-conclusion", response_model=ConclusionChallengeResponse)
def challenge_conclusion_endpoint(request: ConclusionChallengeRequest):
    try:
        return challenge_conclusion(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/intake-candidate", response_model=CandidateIntakeResponse)
def intake_candidate_endpoint(request: CandidateIntakeRequest):
    try:
        return intake_candidate(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/research-search", response_model=GuidedSearchResponse)
def research_search(request: GuidedSearchRequest):
    try:
        return run_guided_search(request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/study-workspace", response_model=StudyWorkspaceResponse)
def study_workspace(request: StudyWorkspaceRequest):
    try:
        return build_study_workspace(request)
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

.workspace-action{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap}.small-btn{padding:8px 10px;font-size:11px;border-radius:9px;background:#edf3ef;color:var(--brand)}
.study-drawer{position:fixed;inset:0;background:rgba(12,25,21,.46);z-index:50;display:none;align-items:stretch;justify-content:flex-end}.study-drawer.open{display:flex}
.drawer-panel{width:min(700px,94vw);height:100%;overflow:auto;background:#fbfcfb;padding:24px;box-shadow:-20px 0 60px rgba(0,0,0,.16)}
.drawer-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;position:sticky;top:-24px;background:#fbfcfb;padding:24px 0 14px;z-index:2;border-bottom:1px solid var(--line)}
.close-btn{width:36px;height:36px;border-radius:10px;background:#edf3ef;color:var(--brand);padding:0}
.readiness{margin:16px 0;background:#edf3ef;border-radius:999px;height:10px;overflow:hidden}.readiness span{display:block;height:100%;background:var(--brand)}
.signal-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.signal{border:1px solid var(--line);background:white;border-radius:12px;padding:11px}.signal b{font-size:12px;display:block}.signal span{font-size:11px;color:var(--muted)}
.signal.observed{border-color:#bcdccc;background:#f2faf6}.req-list{margin:10px 0 0;padding-left:20px;color:#465a52;font-size:13px}.req-list li{margin:5px 0}
.method-note{background:#fff7e5;border:1px solid #ead9aa;padding:13px;border-radius:12px;font-size:12px;color:#654f1d;margin-top:14px}
@media(max-width:560px){.signal-grid{grid-template-columns:1fr}}


.upload-zone{border:1.5px dashed #b7c9c0;border-radius:16px;padding:22px;text-align:center;background:#fafcfb;cursor:pointer;transition:.15s}
.upload-zone:hover,.upload-zone.drag{border-color:#5e8c79;background:#f2f8f5}
.upload-zone input{display:none}.upload-icon{width:46px;height:46px;border-radius:14px;background:#eaf2ee;display:grid;place-items:center;margin:0 auto 9px;font-size:20px;color:var(--brand)}
.upload-zone b{display:block;font-size:14px}.upload-zone span{display:block;font-size:11px;color:var(--muted);margin-top:4px}
.file-pill{display:none;margin-top:10px;padding:9px 11px;border-radius:10px;background:#eaf2ee;color:var(--brand);font-size:12px;font-weight:700;text-align:left}
.pdf-meta{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.pdf-meta span{background:#edf3ef;padding:5px 8px;border-radius:8px;font-size:11px;color:var(--brand)}


.trust-panel{margin:16px 0 0;border:1px solid var(--line);border-radius:18px;background:white;padding:18px}
.trust-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.trust-title{font-size:22px;letter-spacing:-.03em;margin:3px 0}
.trust-banner{padding:12px 13px;border-radius:12px;background:#f4f8f6;margin:12px 0;font-size:13px}
.rob-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:7px;margin-top:10px}
.rob-domain{padding:10px;border-radius:11px;background:#f7f9f8;border:1px solid var(--line)}
.rob-domain b{font-size:11px;display:block}.rob-domain span{font-size:10px;color:var(--muted)}
.rob-domain.low{background:#eff8f3}.rob-domain.some_concerns{background:#fff8e5}.rob-domain.high{background:#fff0ed}.rob-domain.unresolved{background:#f2f3f4}
@media(max-width:700px){.rob-grid{grid-template-columns:1fr 1fr}}


.corpus-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 15px;border:1px solid var(--line);background:#f6f9f7;border-radius:14px;margin:14px 0}
.corpus-count{font-weight:800}.corpus-actions{display:flex;gap:7px;flex-wrap:wrap}.corpus-actions button{padding:8px 10px;font-size:11px}
.synth-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.synth-card{border:1px solid var(--line);background:white;border-radius:18px;padding:18px}
.confidence-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:14px 0}.conf-item{padding:11px;background:#f5f8f6;border-radius:12px}.conf-item b{display:block;font-size:11px;text-transform:uppercase;color:var(--brand2)}.conf-item span{font-size:12px}
.outcome-body{border-top:1px solid var(--line);padding:14px 0}.outcome-body:first-child{border-top:0}.direction-bar{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.direction-chip{font-size:10px;padding:4px 7px;border-radius:999px;background:#edf3ef;color:var(--brand)}
.study-chip{display:inline-flex;gap:6px;align-items:center;padding:6px 8px;border-radius:9px;background:#edf3ef;font-size:11px;margin:3px}
@media(max-width:800px){.synth-grid{grid-template-columns:1fr}.confidence-grid{grid-template-columns:1fr 1fr}}


.gap-card{border:1px solid var(--line);background:#fff;border-radius:14px;padding:14px;margin-top:10px}
.gap-card .gap-type{font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:var(--brand2)}
.gap-actions{display:flex;gap:8px;margin-top:10px;align-items:center;flex-wrap:wrap}
.verdict{display:inline-flex;padding:5px 8px;border-radius:8px;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.verdict.rejected{background:#e8f4ec;color:#276344}.verdict.refined{background:#fff1cc;color:#73530d}.verdict.not_falsified{background:#edf0f2;color:#45565d}.verdict.unresolved{background:#f4e9e6;color:#70483f}
.antigap-result{border-top:1px solid var(--line);padding:9px 0}.antigap-result:first-child{border-top:0}.antigap-class{font-size:9px;text-transform:uppercase;font-weight:800;letter-spacing:.06em}
.antigap-class.direct{color:#276344}.antigap-class.partial{color:#8a6511}.antigap-class.indirect{color:#6c7477}


.challenge-box{margin-top:12px;border:1px solid #cfdcd5;background:#f8fbf9;border-radius:14px;padding:14px}
.challenge-dim{border-top:1px solid var(--line);padding:10px 0}.challenge-dim:first-child{border-top:0}
.sev{display:inline-flex;padding:4px 7px;border-radius:7px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}
.sev.none{background:#e9f4ed;color:#276344}.sev.minor{background:#fff6dc;color:#795c14}.sev.material{background:#ffe9dc;color:#8a4f23}.sev.critical{background:#ffe2de;color:#8c3529}.sev.unresolved{background:#edf0f2;color:#58676d}
.challenge-record{padding:10px 0;border-top:1px solid var(--line)}.challenge-record:first-child{border-top:0}
.challenge-signal{font-size:9px;text-transform:uppercase;font-weight:800;letter-spacing:.06em}
.challenge-signal.potentially_contradictory{color:#973b30}.challenge-signal.potentially_supportive{color:#276344}.challenge-signal.neutral_or_unclear{color:#6c7477}


.intake-status{margin-top:8px;padding:10px 12px;border-radius:11px;background:#f4f8f6;border:1px solid var(--line);font-size:12px}
.intake-status.success{background:#eef8f2}.intake-status.manual{background:#fff8e8}

@media(max-width:900px){.hero-grid,.workspace{grid-template-columns:1fr}.searchgrid{grid-template-columns:1fr}.searchwide{grid-column:auto}.pico{grid-template-columns:1fr 1fr}.form{position:static}.modules{grid-template-columns:1fr 1fr}.summary{grid-template-columns:1fr 1fr}.navlinks{display:none}}@media(max-width:560px){.scope-options{grid-template-columns:1fr}.wrap{padding:0 16px}.hero{padding-top:48px}.modules{grid-template-columns:1fr}.summary{grid-template-columns:1fr 1fr}.metric{grid-template-columns:1fr}.foot{flex-direction:column}}
</style>
</head>
<body>
<nav><div class="wrap" style="width:100%;display:flex;align-items:center;justify-content:space-between"><a class="brand" href="#"><span class="mark">E</span>EvidenceOS <span class="alpha">ALPHA</span></a><div class="navlinks"><a href="#ask">Ask EvidenceOS</a><a href="#workspace">Analyse a study</a><a href="#synthesis">Evidence Synthesis</a><a href="#modules">Platform</a><a href="/docs">API docs</a></div></div></nav>
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

<section id="workspace"><div class="wrap"><div class="kicker">Live workspace</div><h2 class="section-title">Turn a report into an auditable evidence record.</h2><p class="section-sub">Upload the full-text PDF. EvidenceOS extracts machine-readable text, reconstructs sample structure, maps results and flags inconsistencies. Unsupported fields remain unresolved.</p><div class="workspace"><div class="panel form"><h3>Full-text PDF</h3><div class="muted">PDF-only study extraction</div><div class="field"><label>Report ID</label><input id="rid" value="RCT-001"></div><div class="field"><label>Study title</label><input id="ttl" placeholder="Paste the study title"></div><div class="field"><label>Full-text PDF</label>
<label class="upload-zone" id="pdfDrop" for="pdfFile">
  <input id="pdfFile" type="file" accept="application/pdf,.pdf" onchange="pdfSelected()">
  <span class="upload-icon">PDF</span>
  <b>Choose full-text PDF</b>
  <span>or drag and drop a PDF here · max 20 MB</span>
</label>
<div id="filePill" class="file-pill"></div>
</div><div class="actions"><button id="runBtn" class="primary" onclick="runPdf()">Analyse full-text PDF</button></div><div id="err" class="muted" style="margin-top:12px;color:#913f34"></div></div><div class="panel results" id="results"><div class="empty"><div><div class="empty-icon">⌁</div><strong>Your full-text evidence record will appear here.</strong><div class="muted" style="max-width:370px;margin:7px auto">EvidenceOS separates what is reported, what is derived and what remains uncertain.</div></div></div></div></div></div></section>


<section id="synthesis"><div class="wrap">
<div class="kicker">Multi-study workspace</div>
<h2 class="section-title">Evidence Synthesis Workspace.</h2>
<p class="section-sub">Save analysed full-text studies into a local evidence corpus, then inspect outcome patterns, contradictions, uncertainty and methodological coverage. The workspace stays in this browser unless you clear it.</p>
<div class="panel" style="padding:22px">
  <div class="corpus-bar">
    <div><div class="corpus-count"><span id="corpusCount">0</span> saved studies</div><div class="muted">Stored locally in this browser</div></div>
    <div class="corpus-actions"><button class="secondary" onclick="renderCorpus()">Refresh</button><button class="secondary" onclick="clearCorpus()">Clear corpus</button><button id="synthBtn" class="primary" onclick="synthesizeCorpus()">Synthesize evidence</button></div>
  </div>
  <div id="corpusList" style="margin-bottom:16px"></div>
  <div id="synthResults"><div class="empty" style="height:260px"><div><div class="empty-icon">Σ</div><strong>No synthesis yet.</strong><div class="muted">Analyse and save at least one full-text PDF.</div></div></div></div>
</div>
</div></section>
<section id="modules"><div class="wrap"><div class="kicker">Evidence intelligence platform</div><h2 class="section-title">Beyond extraction.</h2><p class="section-sub">The broader EvidenceOS architecture is being validated as separate modules rather than presented as one opaque AI answer.</p><div class="modules"><div class="module"><span class="state">Live alpha</span><h3>Study Workspace</h3><p>Record-level appraisal readiness, full-text handoff, sample flow, arms, outcomes, timepoints, effect estimates and provenance.</p></div><div class="module"><span class="state">Experimental</span><h3>Critical Appraisal</h3><p>Outcome-specific methodological signals and RoB 2 assistance with source-linked rationale.</p></div><div class="module"><span class="state">Live alpha</span><h3>Body of Evidence</h3><p>Stores analysed studies locally and builds outcome-level evidence patterns without collapsing incompatible results.</p></div><div class="module"><span class="state">Experimental</span><h3>Challenge Engine</h3><p>Actively looks for comparator traps, contradictory results and quality asymmetries.</p></div><div class="module"><span class="state">Live alpha</span><h3>Gap Falsification</h3><p>Turns apparent gaps into hypotheses and searches PubMed for counterevidence before calling them research opportunities.</p></div><div class="module"><span class="state">In validation</span><h3>Certainty Calibration</h3><p>Separates effect magnitude from how confidently the evidence supports a conclusion.</p></div></div><div class="foot"><div>EvidenceOS v""" + __version__ + r""" · Research software alpha</div><div>Not a substitute for independent methodological or clinical judgement.</div></div></div></section>
</main>

<div id="studyDrawer" class="study-drawer" onclick="drawerBackdrop(event)">
  <aside class="drawer-panel">
    <div class="drawer-top"><div><div class="kicker">Study Workspace</div><h2 id="drawerTitle" style="margin:3px 0 0;font-size:24px;line-height:1.15"></h2></div><button class="close-btn" onclick="closeStudy()">×</button></div>
    <div id="drawerBody"></div>
  </aside>
</div>


<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function badge(status){const s=status||'unverified';return `<span class="status ${esc(s)}">${esc(s)}</span>`}
function fieldRow(label,f){if(!f)return '';let val=f.value;if(typeof val==='object')val=JSON.stringify(val);return `<div class="row"><span>${esc(label)}</span><div><b>${esc(val)}</b> ${f.unit?`<span class="muted">${esc(f.unit)}</span>`:''} ${badge(f.status)}${f.derivation?`<div class="muted">Derived: ${esc(f.derivation)}</div>`:''}</div></div>`}
function render(rec, detectedDesign=null){
 const samples=rec.sample_sets||[], results=rec.results||[], alarms=rec.alarms||[];
 const grounded=samples.filter(s=>s.total_n&&['verified','derived'].includes(s.total_n.status)).length;
 const html=[];
 html.push(`<div class="block-head"><div><div class="kicker">Universal Evidence Record</div><h3 style="font-size:24px;margin:3px 0 0">${esc(rec.title)}</h3><div class="muted">${esc(rec.report_id)}</div></div>${badge(rec.study_design?.status||'unverified')}</div>`);
 html.push(`<div class="summary"><div class="stat"><strong>${samples.length}</strong><small>Sample sets</small></div><div class="stat"><strong>${results.length}</strong><small>Results mapped</small></div><div class="stat"><strong>${alarms.length}</strong><small>Consistency alarms</small></div><div class="stat"><strong>${grounded}</strong><small>Grounded sample fields</small></div></div>`);
 const designField=detectedDesign?{value:detectedDesign,status:'derived',derivation:'Detected from uploaded full-text PDF by the EvidenceOS design router.'}:rec.study_design;
 html.push(`<div class="block"><h4>Study identity</h4><div class="record">${fieldRow('Design',designField)}${fieldRow('Trial registration',rec.trial_registration)}</div></div>`);
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
   return `<div class="paper" data-elig="${esc(e.overall)}"><div class="paper-head"><div style="min-width:0"><div>${db}</div><div class="paper-title">${esc(p.title)}</div></div><span class="elig ${esc(e.overall)}">${esc(e.overall||'uncertain')}</span></div><div class="design">${esc(d.final_label||'uncertain design')} · confidence ${Math.round((d.confidence||0)*100)}%</div><div class="paper-meta">${esc(ident)}</div>${p.abstract?`<div class="paper-abstract">${esc(p.abstract)}</div>`:''}<details style="margin-top:8px"><summary class="muted" style="cursor:pointer">Why this classification?</summary><div class="muted" style="margin-top:6px">${esc(e.exclusion_reason||((e.dimensions||[]).map(y=>`${y.dimension}: ${y.judgement}`).join(' · '))||'No rationale available.')}</div></details><div class="workspace-action"><button class="small-btn" onclick="openStudyById('${esc(p.record_id)}')">Open Study Workspace →</button></div></div>`;
 }).join('')||'<div class="record muted">No records in this category.</div>';
}

function openStudyById(recordId){
 const item=(window._eosIntel||[]).find(x=>x.record?.record_id===recordId);
 if(!item)return;
 openStudyWorkspace(item);
}
async function openStudyWorkspace(item){
 const drawer=document.getElementById('studyDrawer'), body=document.getElementById('drawerBody');
 document.getElementById('drawerTitle').textContent=item.record?.title||'Study';
 drawer.classList.add('open');document.body.style.overflow='hidden';
 body.innerHTML='<div class="empty" style="height:250px"><div><span class="spinner" style="border-color:#173f3544;border-top-color:#173f35"></span><div class="muted">Building appraisal scaffold…</div></div></div>';
 try{
   const r=await fetch('/v1/study-workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:item.record,design:item.design,eligibility:item.eligibility})});
   const raw=await r.text();let data=null;try{data=JSON.parse(raw)}catch(_){}
   if(!r.ok)throw new Error(data?.detail||`Study workspace failed (HTTP ${r.status})`);
   renderStudyWorkspace(data);
 }catch(e){body.innerHTML=`<div class="record" style="color:#913f34">${esc(e.message)}</div>`}
}
function renderStudyWorkspace(d){
 const p=d.record||{}, design=d.design||{}, elig=d.eligibility||{};
 const meta=[p.year,p.journal,p.pmid?`PMID ${p.pmid}`:'',p.doi?`DOI ${p.doi}`:''].filter(Boolean).join(' · ');
 const signals=(d.observed_signals||[]).map(s=>`<div class="signal ${s.status==='observed'?'observed':''}"><b>${esc(s.signal)}</b><span>${s.status==='observed'?'Observed in title/abstract':'Not observed in abstract'}${s.evidence?` · “${esc(s.evidence)}”`:''}</span></div>`).join('');
 const dims=(elig.dimensions||[]).map(x=>`<div class="row"><span>${esc(x.dimension)}</span><div><b>${esc(x.judgement)}</b><div class="muted">${esc(x.rationale||'')}</div></div></div>`).join('');
 const req=(d.required_full_text_information||[]).map(x=>`<li>${esc(x)}</li>`).join('');
 document.getElementById('drawerBody').innerHTML=`
 <div class="paper-meta" style="margin-top:14px">${esc(meta)}</div>
 <div class="summary" style="grid-template-columns:repeat(3,1fr)">
   <div class="stat"><strong>${esc(design.final_label||'uncertain')}</strong><small>Predicted design</small></div>
   <div class="stat"><strong>${esc(elig.overall||'uncertain')}</strong><small>Eligibility signal</small></div>
   <div class="stat"><strong>${esc(d.appraisal_tool)}</strong><small>Appraisal framework</small></div>
 </div>
 <div class="block"><div class="block-head"><h4>Appraisal readiness</h4><b>${esc(d.readiness_score)}%</b></div><div class="readiness"><span style="width:${Number(d.readiness_score)||0}%"></span></div><div class="muted">This measures information available for appraisal, not study quality.</div></div>
 <div class="block"><h4>Signals observable from PubMed</h4><div class="signal-grid" style="margin-top:10px">${signals}</div></div>
 <div class="block"><h4>Eligibility against your PICO</h4><div class="record">${dims||'<span class="muted">No dimension-level rationale available.</span>'}</div></div>
 <div class="block"><h4>What EvidenceOS still needs</h4><ul class="req-list">${req}</ul><div class="method-note">${esc(d.methodological_note)}</div></div>
 ${p.abstract?`<div class="block"><h4>Abstract</h4><div class="record">${esc(p.abstract)}</div></div>`:''}
 <div class="block"><div class="actions"><button type="button" class="primary" onclick="sendStudyToFullTextById()">Continue to full-text analysis →</button></div><div class="muted" style="margin-top:8px">Upload the full-text PDF in the Study Extraction workspace. RoB 2 will only become valid once outcome-specific full-text evidence is available.</div></div>`;
 window._activeStudy={record_id:p.record_id||'STUDY',title:p.title||''};
}
function sendStudyToFullTextById(){
 const x=window._activeStudy||{};
 document.getElementById('rid').value=x.record_id||'STUDY';
 document.getElementById('ttl').value=x.title||'';
 closeStudy();
 const workspace=document.getElementById('workspace');
 if(workspace)workspace.scrollIntoView({behavior:'smooth',block:'start'});
 setTimeout(()=>{
   const input=document.getElementById('pdfFile');
   if(input)input.click();
 },650);
}
function closeStudy(){document.getElementById('studyDrawer').classList.remove('open');document.body.style.overflow=''}
function drawerBackdrop(e){if(e.target.id==='studyDrawer')closeStudy()}

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


const CORPUS_KEY='evidenceos_v7_corpus';

function getCorpus(){
 try{return JSON.parse(localStorage.getItem(CORPUS_KEY)||'[]')}catch(_){return []}
}
function setCorpus(items){
 localStorage.setItem(CORPUS_KEY,JSON.stringify(items));renderCorpus();
}
function saveCurrentStudy(){
 const s=window._lastAnalysedStudy;if(!s)return;
 const items=getCorpus();
 const idx=items.findIndex(x=>x.report_id===s.report_id);
 if(idx>=0)items[idx]=s;else items.push(s);
 setCorpus(items);
 document.getElementById('synthesis').scrollIntoView({behavior:'smooth'});
}
function removeCorpusStudy(reportId){
 setCorpus(getCorpus().filter(x=>x.report_id!==reportId));
}
function clearCorpus(){
 if(!confirm('Clear all locally saved EvidenceOS studies from this browser?'))return;
 setCorpus([]);document.getElementById('synthResults').innerHTML='<div class="empty" style="height:260px"><div><strong>Corpus cleared.</strong></div></div>';
}
function renderCorpus(){
 const items=getCorpus(),count=document.getElementById('corpusCount'),root=document.getElementById('corpusList');
 if(count)count.textContent=items.length;
 if(!root)return;
 root.innerHTML=items.length?items.map(s=>`<span class="study-chip"><b>${esc(s.title)}</b> · ${esc(s.design)} <button style="padding:2px 5px;background:transparent;color:#7b4b43" onclick="removeCorpusStudy('${esc(s.report_id)}')">×</button></span>`).join(''):'<div class="muted">No studies saved yet.</div>';
}
async function synthesizeCorpus(){
 const items=getCorpus(),btn=document.getElementById('synthBtn'),root=document.getElementById('synthResults');
 if(!items.length){root.innerHTML='<div class="record">Save at least one analysed PDF first.</div>';return}
 btn.disabled=true;btn.innerHTML='<span class="spinner"></span>Synthesizing';
 try{
   const r=await fetch('/v1/synthesize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:document.getElementById('qtext')?.value||null,studies:items})});
   const raw=await r.text();let d=null;try{d=JSON.parse(raw)}catch(_){}
   if(!r.ok)throw new Error(d?.detail||`Synthesis failed (HTTP ${r.status})`);
   renderSynthesis(d);
 }catch(e){root.innerHTML=`<div class="record" style="color:#913f34">${esc(e.message)}</div>`}
 finally{btn.disabled=false;btn.textContent='Synthesize evidence'}
}

async function falsifyGap(g){
 const root=document.getElementById(`gap-result-${g.gap_id}`);
 if(!root)return;
 const population=document.getElementById('qpop')?.value?.trim()||'unspecified population';
 const intervention=document.getElementById('qint')?.value?.trim()||'unspecified intervention';
 const comparator=document.getElementById('qcomp')?.value?.trim()||'';
 const timepoint=document.getElementById('qtime')?.value?.trim()||'';
 root.innerHTML='<div class="muted" style="margin-top:10px"><span class="spinner" style="border-color:#173f3544;border-top-color:#173f35"></span>Trying to falsify this gap on PubMed…</div>';
 try{
   const r=await fetch('/v1/falsify-gap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     gap_id:g.gap_id,gap_type:g.gap_type,topic:g.topic,statement:g.statement,
     population,intervention,comparator,timepoint,max_results:15
   })});
   const raw=await r.text();let d=null;try{d=JSON.parse(raw)}catch(_){}
   if(!r.ok)throw new Error(d?.detail||`Gap falsification failed (HTTP ${r.status})`);
   const records=(d.records||[]).slice(0,8).map(x=>`<div class="antigap-result"><div class="antigap-class ${esc(x.classification)}">${esc(x.classification)}</div><b style="font-size:12px">${esc(x.title)}</b><div class="muted">${esc([x.year,x.journal,x.pmid?`PMID ${x.pmid}`:''].filter(Boolean).join(' · '))}</div><div class="muted">${esc(x.rationale)}</div></div>`).join('');
   root.innerHTML=`<div class="record" style="margin-top:10px"><div class="block-head"><b>Gap falsification result</b><span class="verdict ${esc(d.verdict)}">${esc(d.verdict)}</span></div><div style="margin-top:8px">${esc(d.interpretation)}</div>${d.revised_gap?`<div class="alarm info"><b>Refined statement</b><div>${esc(d.revised_gap)}</div></div>`:''}<div class="row"><span>Records examined</span><b>${d.records_examined}</b></div><div class="row"><span>Direct counterevidence</span><b>${d.direct_evidence}</b></div><div class="row"><span>Partial counterevidence</span><b>${d.partial_evidence}</b></div><details style="margin-top:10px"><summary class="muted" style="cursor:pointer">Anti-gap search provenance</summary><div class="muted" style="margin-top:6px"><b>PubMed query</b><br>${esc(d.anti_gap_query)}</div><div style="margin-top:8px">${records||'<span class="muted">No records returned.</span>'}</div><div class="method-note">${esc(d.negative_search_caveat)}</div></details></div>`;
 }catch(e){root.innerHTML=`<div class="alarm critical">${esc(e.message)}</div>`}
}


function safeId(x){return String(x||'outcome').replace(/[^a-zA-Z0-9_-]/g,'_').slice(0,80)}

async function intakeCandidate(candidate,button){
 const card=button.closest('.challenge-record');
 const slot=card?.querySelector('.intake-slot');
 button.disabled=true;button.textContent='Checking full text…';
 if(slot)slot.innerHTML='<div class="intake-status">Checking PMC availability and reuse status…</div>';
 try{
   const r=await fetch('/v1/intake-candidate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(candidate)});
   const raw=await r.text();let d=null;try{d=JSON.parse(raw)}catch(_){}
   if(!r.ok)throw new Error(d?.detail||`Candidate intake failed (HTTP ${r.status})`);

   if(d.mode==='auto_imported' && d.record && d.trust_assessment){
     const s={
       report_id:d.report_id,
       title:d.title,
       design:d.trust_assessment.design||'other',
       framework:d.trust_assessment.framework||null,
       trust_overall:d.trust_assessment.overall_judgement||null,
       record:d.record,
       trust_assessment:d.trust_assessment,
       provenance:{source:'PMC reusable full text',pmcid:d.pmcid||null,license:d.license||null}
     };
     const items=getCorpus();
     const idx=items.findIndex(x=>x.report_id===s.report_id);
     if(idx>=0)items[idx]=s;else items.push(s);
     setCorpus(items);
     if(slot)slot.innerHTML=`<div class="intake-status success"><b>Added automatically.</b><br>${esc(d.message)}${d.pmcid?`<br>PMC: ${esc(d.pmcid)} · License: ${esc(d.license||'not reported')}`:''}</div>`;
     button.textContent='Added to corpus';
     document.getElementById('synthesis').scrollIntoView({behavior:'smooth'});
     setTimeout(()=>synthesizeCorpus(),650);
     return;
   }

   window._pendingCandidate={
     report_id:d.report_id,
     title:d.title,
     pmid:d.pmid||null,
     doi:d.doi||null,
     pmcid:d.pmcid||null,
     license:d.license||null
   };
   document.getElementById('rid').value=d.report_id||'CANDIDATE';
   document.getElementById('ttl').value=d.title||candidate.title||'';
   if(slot)slot.innerHTML=`<div class="intake-status manual"><b>PDF required.</b><br>${esc(d.message)}</div>`;
   button.disabled=false;button.textContent='Choose PDF →';
   button.onclick=()=>{
     document.getElementById('workspace').scrollIntoView({behavior:'smooth'});
     setTimeout(()=>document.getElementById('pdfFile')?.click(),650);
   };
   document.getElementById('workspace').scrollIntoView({behavior:'smooth'});
   setTimeout(()=>document.getElementById('pdfFile')?.click(),750);
 }catch(e){
   if(slot)slot.innerHTML=`<div class="alarm critical">${esc(e.message)}</div>`;
   button.disabled=false;button.textContent='Retry intake';
 }
}

async function challengeOutcome(o){
 const root=document.getElementById(`challenge-${safeId(o.outcome)}`);
 if(!root)return;
 const population=document.getElementById('qpop')?.value?.trim()||'unspecified population';
 const intervention=document.getElementById('qint')?.value?.trim()||'unspecified intervention';
 const comparator=document.getElementById('qcomp')?.value?.trim()||'';
 const timepoint=document.getElementById('qtime')?.value?.trim()||'';
 root.innerHTML='<div class="challenge-box muted"><span class="spinner" style="border-color:#173f3544;border-top-color:#173f35"></span>Challenging the conclusion against the stored corpus and PubMed…</div>';
 try{
   const r=await fetch('/v1/challenge-conclusion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     outcome:o.outcome,
     dominant_direction:o.dominant_direction,
     directions:o.directions||{},
     studies_in_body:o.studies,
     methodological_support:o.methodological_support,
     population,intervention,comparator,timepoint,max_results:15
   })});
   const raw=await r.text();let d=null;try{d=JSON.parse(raw)}catch(_){}
   if(!r.ok)throw new Error(d?.detail||`Conclusion challenge failed (HTTP ${r.status})`);
   const dims=(d.dimensions||[]).map(x=>`<div class="challenge-dim"><div class="block-head"><b>${esc(x.dimension.replaceAll('_',' '))}</b><span class="sev ${esc(x.severity)}">${esc(x.severity)}</span></div><div class="muted">${esc(x.rationale)}</div></div>`).join('');
   const records=(d.records||[]).slice(0,10).map(x=>`<div class="challenge-record"><div class="block-head"><span class="challenge-signal ${esc(x.challenge_signal)}">${esc(x.challenge_signal.replaceAll('_',' '))}</span><span class="db">${esc(x.evidence_level)}</span></div><b style="font-size:12px">${esc(x.title)}</b><div class="muted">${esc([x.year,x.journal,x.pmid?`PMID ${x.pmid}`:''].filter(Boolean).join(' · '))}</div><div class="muted">${esc(x.rationale)}</div>${x.relevance!=='indirect'?`<div class="gap-actions"><button class="small-btn" onclick='intakeCandidate(${JSON.stringify({title:x.title,pmid:x.pmid||null,doi:x.doi||null})},this)'>Add to evidence corpus →</button></div><div class="intake-slot"></div>`:''}</div>`).join('');
   const verdictClass=d.verdict==='materially_weakened'?'critical':d.verdict==='survived'?'verified':'warning';
   root.innerHTML=`<div class="challenge-box"><div class="block-head"><div><div class="kicker">Challenge verdict</div><b>${esc(d.verdict.replaceAll('_',' '))}</b></div><span class="status ${verdictClass}">${esc(d.verdict)}</span></div><div class="alarm info" style="margin-top:10px"><b>Revised conclusion</b><div>${esc(d.revised_conclusion)}</div></div><div style="margin-top:10px">${dims}</div><div class="row"><span>PubMed records examined</span><b>${d.records_examined}</b></div><div class="row"><span>Potential contradictions</span><b>${d.potential_contradictions}</b></div><div class="row"><span>Higher-level challenges</span><b>${d.higher_level_challenges}</b></div><details style="margin-top:10px"><summary class="muted" style="cursor:pointer">External challenge provenance</summary><div class="muted" style="margin-top:7px"><b>Adversarial PubMed query</b><br>${esc(d.external_query)}</div><div style="margin-top:8px">${records||'<span class="muted">No records returned.</span>'}</div><div class="method-note">${esc(d.interpretation_boundary)}</div></details></div>`;
 }catch(e){root.innerHTML=`<div class="alarm critical">${esc(e.message)}</div>`}
}

function renderSynthesis(d){
 const c=d.confidence||{};
 const outcomes=(d.outcomes||[]).map(o=>{
   const chips=Object.entries(o.directions||{}).map(([k,v])=>`<span class="direction-chip">${esc(k)}: ${v}</span>`).join('');
   return `<div class="outcome-body"><div class="block-head"><div><b>${esc(o.outcome)}</b><div class="muted">${o.studies} study/studies · ${o.results} extracted result(s)</div></div><span class="status ${o.consistency==='consistent'?'verified':'warning'}">${esc(o.consistency)}</span></div><div class="direction-bar">${chips}</div><div class="muted" style="margin-top:8px">${esc(o.interpretation)}</div><div class="row"><span>Precision</span><b>${esc(o.precision)}</b></div><div class="row"><span>Methodological support</span><b>${esc(o.methodological_support)}</b></div><div class="gap-actions"><button class="small-btn" onclick='challengeOutcome(${JSON.stringify(o)})'>Challenge this conclusion →</button><span class="muted">Try to prove the current interpretation wrong</span></div><div id="challenge-${safeId(o.outcome)}"></div></div>`;
 }).join('');
 const contradictions=(d.contradictions||[]).map(x=>`<div class="alarm warning">${esc(x)}</div>`).join('');
 const gaps=(d.gaps||[]).map(x=>`<div class="alarm info">${esc(x)}</div>`).join('');
 const gapHyp=(d.gap_hypotheses||[]).map(g=>`<div class="gap-card" id="card-${esc(g.gap_id)}"><div class="gap-type">${esc(g.gap_type)} hypothesis</div><b>${esc(g.statement)}</b><div class="muted" style="margin-top:5px">${esc(g.reason)}</div><div class="gap-actions"><button class="small-btn" onclick='falsifyGap(${JSON.stringify(g)})'>Challenge this gap →</button><span class="muted">Search PubMed for counterevidence</span></div><div id="gap-result-${esc(g.gap_id)}"></div></div>`).join('');
 document.getElementById('synthResults').innerHTML=`
 <div class="synth-card" style="margin-bottom:16px"><div class="kicker">What does the evidence suggest?</div><h3 style="font-size:25px;margin:4px 0">${esc(d.headline)}</h3><div class="muted">${esc(d.interpretation_boundary)}</div></div>
 <div class="synth-card" style="margin-bottom:16px"><div class="kicker">How resolved is the evidence?</div><h3 style="margin:4px 0">${esc(c.overall_label)}</h3><div class="confidence-grid"><div class="conf-item"><b>Quantity</b><span>${esc(c.quantity)}</span></div><div class="conf-item"><b>Consistency</b><span>${esc(c.consistency)}</span></div><div class="conf-item"><b>Methodology</b><span>${esc(c.methodological_trust)}</span></div><div class="conf-item"><b>Precision</b><span>${esc(c.precision)}</span></div><div class="conf-item"><b>Directness</b><span>${esc(c.directness)}</span></div></div>${(c.rationale||[]).map(x=>`<div class="muted">• ${esc(x)}</div>`).join('')}</div>
 <div class="synth-grid"><div class="synth-card"><div class="kicker">Outcome bodies</div>${outcomes||'<div class="muted">No outcome-level evidence available.</div>'}</div><div><div class="synth-card"><div class="kicker">Contradictions</div>${contradictions||'<div class="muted">No explicit directional contradiction detected.</div>'}</div><div class="synth-card" style="margin-top:16px"><div class="kicker">What remains uncertain?</div>${gaps||'<div class="muted">No broad uncertainty automatically detected.</div>'}<div style="margin-top:14px"><b>Falsifiable gap hypotheses</b><div class="muted">EvidenceOS treats each apparent gap as a hypothesis and actively searches for counterevidence before calling it a research opportunity.</div>${gapHyp||'<div class="record muted">No falsifiable gap hypothesis generated from this corpus.</div>'}</div></div></div></div>`;
}
window.addEventListener('DOMContentLoaded',renderCorpus);

function pdfSelected(){
 const f=document.getElementById('pdfFile').files[0];
 const pill=document.getElementById('filePill');
 if(!f){pill.style.display='none';pill.textContent='';return}
 if(!f.name.toLowerCase().endsWith('.pdf')){
   pill.style.display='block';pill.textContent='Only PDF files are supported.';return
 }
 pill.style.display='block';
 pill.textContent=`${f.name} · ${(f.size/1024/1024).toFixed(2)} MB`;
}

function renderTrustAssessment(t){
 if(!t)return '';
 const framework=`<span class="status warning">${esc(t.framework)}</span>`;
 const genericDomains=(t.domains||[]).map(d=>`<div class="rob-domain ${d.judgement==='signal_present'?'low':'unresolved'}"><b>${esc(d.domain)}</b><span>${esc(d.rationale)}</span></div>`).join('');
 const outcomes=(t.outcome_assessments||[]).map(a=>{
   const domains=(a.domains||[]).map(d=>`<div class="rob-domain ${esc(d.judgement)}"><b>${esc(d.domain_id)} · ${esc(d.judgement)}</b><span>${esc(d.domain_name)}</span></div>`).join('');
   return `<div class="record" style="margin-top:12px"><div class="block-head"><div><b>${esc(a.outcome||'Outcome')}</b><div class="muted">${esc([a.timepoint,a.effect_measure].filter(Boolean).join(' · '))}</div></div><span class="status ${a.overall_judgement==='low'?'verified':a.overall_judgement==='high'?'critical':'warning'}">${esc(a.overall_judgement)}</span></div><div class="rob-grid">${domains}</div><details style="margin-top:10px"><summary class="muted" style="cursor:pointer">Why this judgement?</summary><div class="muted" style="margin-top:6px">${esc(a.overall_rationale||'')}</div></details></div>`;
 }).join('');
 const limitations=(t.limitations||[]).length?`<div class="method-note"><b>Interpretation limits</b><ul class="req-list">${t.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:'';
 return `<div class="trust-panel"><div class="trust-head"><div><div class="kicker">How much can we trust this study?</div><h3 class="trust-title">${esc(t.headline)}</h3><div class="muted">Detected design: ${esc(t.design)}</div></div>${framework}</div><div class="trust-banner">${esc(t.explanation)}</div>${genericDomains?`<div class="rob-grid">${genericDomains}</div>`:''}${outcomes}${limitations}</div>`;
}
async function runPdf(){
 const btn=document.getElementById('runBtn'),err=document.getElementById('err');
 const f=document.getElementById('pdfFile').files[0];err.textContent='';
 if(!ttl.value.trim()){err.textContent='Add the study title.';return}
 if(!f){err.textContent='Choose the full-text PDF.';return}
 if(!f.name.toLowerCase().endsWith('.pdf')){err.textContent='Only PDF files are supported.';return}
 const form=new FormData();
 form.append('report_id',rid.value||'STUDY');
 form.append('title',ttl.value);
 form.append('file',f);
 btn.disabled=true;btn.innerHTML='<span class="spinner"></span>Analysing PDF';
 try{
   const response=await fetch('/v1/extract-pdf',{method:'POST',body:form});
   const raw=await response.text();
   let data=null;try{data=JSON.parse(raw)}catch(_){}
   if(!response.ok){
     if(data?.detail)throw new Error(data.detail);
     if(raw.trim().startsWith('<'))throw new Error(`EvidenceOS backend returned an HTML error page (HTTP ${response.status}).`);
     throw new Error(raw.slice(0,300)||`PDF analysis failed (HTTP ${response.status})`);
   }
   if(!data?.record)throw new Error('EvidenceOS returned an invalid PDF analysis response.');
   render(data.record,data.trust_assessment?.design||null);
   window._lastAnalysedStudy={
     report_id:rid.value||data.record.report_id,
     title:ttl.value||data.record.title,
     design:data.trust_assessment?.design||'other',
     framework:data.trust_assessment?.framework||null,
     trust_overall:data.trust_assessment?.overall_judgement||null,
     record:data.record,
     trust_assessment:data.trust_assessment,
     provenance:window._pendingCandidate?{source:'user uploaded PDF for challenge candidate',pmid:window._pendingCandidate.pmid||null,doi:window._pendingCandidate.doi||null,pmcid:window._pendingCandidate.pmcid||null,license:window._pendingCandidate.license||null}:{source:'user uploaded PDF'}
   };
   const shouldAutoSave=!!window._pendingCandidate;
   window._pendingCandidate=null;
   const results=document.getElementById('results');
   results.insertAdjacentHTML('beforeend',renderTrustAssessment(data.trust_assessment));
   const meta=document.createElement('div');
   meta.className='pdf-meta';
   meta.innerHTML=`<span>${esc(data.filename)}</span><span>${esc(data.pages)} pages</span><span>${esc(data.extracted_characters)} extracted characters</span>`;
   results.insertBefore(meta,results.firstChild);
   const save=document.createElement('div');
   save.className='corpus-bar';
   save.innerHTML='<div><b>Add this study to the Evidence Synthesis corpus</b><div class="muted">The full analysis summary will be stored locally in this browser.</div></div><button class="primary" onclick="saveCurrentStudy()">Save study</button>';
   results.insertBefore(save,meta.nextSibling);
   if(shouldAutoSave){
     const items=getCorpus(),s=window._lastAnalysedStudy;
     const idx=items.findIndex(x=>x.report_id===s.report_id);
     if(idx>=0)items[idx]=s;else items.push(s);
     setCorpus(items);
     save.innerHTML='<div><b>Challenge candidate added to corpus.</b><div class="muted">EvidenceOS will recalculate the synthesis automatically.</div></div><span class="status verified">saved</span>';
     setTimeout(()=>{document.getElementById('synthesis').scrollIntoView({behavior:'smooth'});synthesizeCorpus()},750);
   }
 }catch(e){err.textContent=e.message}
 finally{btn.disabled=false;btn.textContent='Analyse full-text PDF'}
}
const drop=document.getElementById('pdfDrop');
['dragenter','dragover'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('drag')}));
['dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('drag')}));
drop.addEventListener('drop',e=>{
 const files=e.dataTransfer.files;
 if(files&&files[0]){
   const dt=new DataTransfer();dt.items.add(files[0]);
   document.getElementById('pdfFile').files=dt.files;pdfSelected();
 }
});
</script>
</body>
</html>""")
