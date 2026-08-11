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
from .project_workspace import ProjectValidationRequest, ProjectValidationResponse, validate_project

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


@app.post("/v1/project/validate", response_model=ProjectValidationResponse)
def validate_project_endpoint(request: ProjectValidationRequest):
    try:
        return validate_project(request)
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


.project-shell{border:1px solid var(--line);background:white;border-radius:20px;padding:18px;box-shadow:0 8px 28px rgba(16,34,28,.04)}
.project-grid{display:grid;grid-template-columns:1.3fr 1fr auto;gap:10px;align-items:end}
.project-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.project-pill{padding:6px 9px;border-radius:9px;background:#edf3ef;font-size:11px;color:var(--brand)}
.history-list{display:grid;gap:8px;margin-top:12px;max-height:280px;overflow:auto}
.history-event{border-left:3px solid #cbd9d2;padding:9px 11px;background:#f8faf9;border-radius:0 10px 10px 0}
.history-event b{font-size:12px}.history-event span{display:block;font-size:10px;color:var(--muted);margin-top:2px}
.graph-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:white;padding:12px}
.graph-legend{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.graph-legend span{font-size:10px;padding:5px 8px;border-radius:999px;background:#edf3ef}
.graph-node rect{stroke:#cad8d1;stroke-width:1}.graph-node text{font-size:11px;fill:#173f35}.graph-edge{stroke:#b8c8c0;stroke-width:1.2}
.graph-study rect{fill:#f7faf8}.graph-outcome rect{fill:#eef6f2}.graph-gap rect{fill:#fff8e8}.graph-challenge rect{fill:#fff0ed}.graph-question rect{fill:#173f35}.graph-question text{fill:white}
.graph-empty{padding:40px;text-align:center;color:var(--muted)}
.storage-meter{height:6px;background:#edf1ef;border-radius:999px;overflow:hidden;margin-top:6px}.storage-meter span{display:block;height:100%;background:#6d9d89}
@media(max-width:800px){.project-grid{grid-template-columns:1fr}}


.lang-switch{display:flex;gap:3px;padding:3px;border:1px solid var(--line);border-radius:10px;background:white;margin-left:14px}
.lang-switch button{padding:6px 8px;border-radius:7px;background:transparent;color:var(--muted);font-size:11px;font-weight:800}
.lang-switch button.active{background:var(--brand);color:white}
.nav-right{display:flex;align-items:center}
@media(max-width:900px){.lang-switch{margin-left:0}}

@media(max-width:900px){.hero-grid,.workspace{grid-template-columns:1fr}.searchgrid{grid-template-columns:1fr}.searchwide{grid-column:auto}.pico{grid-template-columns:1fr 1fr}.form{position:static}.modules{grid-template-columns:1fr 1fr}.summary{grid-template-columns:1fr 1fr}.navlinks{display:none}}@media(max-width:560px){.scope-options{grid-template-columns:1fr}.wrap{padding:0 16px}.hero{padding-top:48px}.modules{grid-template-columns:1fr}.summary{grid-template-columns:1fr 1fr}.metric{grid-template-columns:1fr}.foot{flex-direction:column}}
</style>
</head>
<body>
<nav><div class="wrap" style="width:100%;display:flex;align-items:center;justify-content:space-between"><a class="brand" href="#"><span class="mark">E</span>EvidenceOS <span class="alpha">ALPHA</span></a><div class="nav-right"><div class="navlinks"><a href="#project">Project</a><a href="#ask">Ask EvidenceOS</a><a href="#workspace">Analyse a study</a><a href="#synthesis">Evidence Synthesis</a><a href="#evidenceGraph">Evidence Graph</a><a href="#modules">Platform</a><a href="/docs">API docs</a></div><div class="lang-switch" aria-label="Language"><button type="button" data-lang-choice="en" onclick="setLanguage('en')">EN</button><button type="button" data-lang-choice="it" onclick="setLanguage('it')">IT</button></div></div></div></nav>
<main>
<section class="hero"><div class="wrap"><span class="eyebrow"><span class="dot"></span> Auditable evidence intelligence</span><h1>Evidence you can inspect,<br>not just summaries you can read.</h1><div class="hero-grid"><div><p class="lede">EvidenceOS reconstructs the path from scientific reports to structured evidence, preserving provenance and surfacing contradictions before they become conclusions.</p><a href="#workspace"><button class="primary" style="padding:14px 18px">Analyse a study →</button></a></div><div class="hero-card"><div class="kicker">Current public alpha</div><div class="metric"><div><b>Source-linked</b><span>Every direct field carries provenance</span></div><div><b>Field-level</b><span>Verified, derived or unresolved</span></div><div><b>Adversarial</b><span>Consistency alarms challenge outputs</span></div></div></div></div></div></section>



<section id="project"><div class="wrap">
<div class="kicker">Persistent research workspace</div>
<h2 class="section-title">EvidenceOS Project.</h2>
<p class="section-sub">Keep the question, analysed studies, synthesis revisions, challenges and gaps together as one portable scientific project.</p>
<div class="project-shell">
  <div class="project-grid">
    <div class="field" style="margin-top:0"><label>Active project</label><select id="projectSelect" onchange="switchProject(this.value)" style="width:100%;border:1px solid var(--line);border-radius:13px;padding:12px 13px;background:white"></select></div>
    <div class="field" style="margin-top:0"><label>Project name</label><input id="projectName" placeholder="My evidence project" onchange="renameActiveProject(this.value)"></div>
    <div class="actions" style="margin:0"><button class="secondary" onclick="newProject()">New</button><button class="secondary" onclick="exportProject()">Export JSON</button><button class="secondary" onclick="document.getElementById('projectImport').click()">Import</button><input id="projectImport" type="file" accept="application/json,.json" style="display:none" onchange="importProjectFile(this)"></div>
  </div>
  <div class="project-meta">
    <span class="project-pill" id="projectIdPill">Project —</span>
    <span class="project-pill"><span id="projectStudyCount">0</span> studies</span>
    <span class="project-pill"><span id="projectRevisionCount">0</span> revisions</span>
    <span class="project-pill" id="projectUpdated">Not saved yet</span>
  </div>
  <div style="margin-top:15px"><div class="block-head"><b>Revision history</b><button class="small-btn" onclick="renderProjectHistory()">Refresh</button></div><div id="projectHistory" class="history-list"></div></div>
  <div class="muted" style="margin-top:12px">Browser persistence is the alpha storage layer. Export the project JSON for a portable backup; imported JSON is validated by the EvidenceOS backend before activation.</div>
  <div class="storage-meter"><span id="storageMeter" style="width:0%"></span></div>
  <div class="muted" id="storageLabel" style="margin-top:4px"></div>
</div>
</div></section>
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
<p class="section-sub">Save analysed full-text studies into a local evidence corpus, then inspect outcome patterns, contradictions, uncertainty and methodological coverage. The corpus belongs to the active EvidenceOS Project and is restored when you reopen that project in this browser.</p>
<div class="panel" style="padding:22px">
  <div class="corpus-bar">
    <div><div class="corpus-count"><span id="corpusCount">0</span> saved studies</div><div class="muted">Stored locally in this browser</div></div>
    <div class="corpus-actions"><button class="secondary" onclick="renderCorpus()">Refresh</button><button class="secondary" onclick="clearCorpus()">Clear corpus</button><button id="synthBtn" class="primary" onclick="synthesizeCorpus()">Synthesize evidence</button></div>
  </div>
  <div id="corpusList" style="margin-bottom:16px"></div>
  <div id="synthResults"><div class="empty" style="height:260px"><div><div class="empty-icon">Σ</div><strong>No synthesis yet.</strong><div class="muted">Analyse and save at least one full-text PDF.</div></div></div></div>
</div>
</div></section>

<section id="evidenceGraph"><div class="wrap">
<div class="kicker">Epistemic provenance map</div>
<h2 class="section-title">Evidence Graph.</h2>
<p class="section-sub">Inspect the current project as a graph: research question → full-text studies → outcome bodies → challenges and gap hypotheses. The graph represents relationships, not causal certainty.</p>
<div class="graph-legend"><span>Question</span><span>Study</span><span>Outcome body</span><span>Challenge</span><span>Gap hypothesis</span></div>
<div class="graph-wrap"><div id="graphRoot" class="graph-empty">Run or restore an Evidence Synthesis to build the graph.</div></div>
</div></section>
<section id="modules"><div class="wrap"><div class="kicker">Evidence intelligence platform</div><h2 class="section-title">Beyond extraction.</h2><p class="section-sub">The broader EvidenceOS architecture is being validated as separate modules rather than presented as one opaque AI answer.</p><div class="modules"><div class="module"><span class="state">Live alpha</span><h3>Study Workspace</h3><p>Record-level appraisal readiness, full-text handoff, sample flow, arms, outcomes, timepoints, effect estimates and provenance.</p></div><div class="module"><span class="state">Experimental</span><h3>Critical Appraisal</h3><p>Outcome-specific methodological signals and RoB 2 assistance with source-linked rationale.</p></div><div class="module"><span class="state">Live alpha</span><h3>Project + Evidence Graph</h3><p>Persists question, studies, synthesis revisions, challenge history and gap hypotheses as one exportable project with an inspectable evidence graph.</p></div><div class="module"><span class="state">Experimental</span><h3>Challenge Engine</h3><p>Actively looks for comparator traps, contradictory results and quality asymmetries.</p></div><div class="module"><span class="state">Live alpha</span><h3>Gap Falsification</h3><p>Turns apparent gaps into hypotheses and searches PubMed for counterevidence before calling them research opportunities.</p></div><div class="module"><span class="state">In validation</span><h3>Certainty Calibration</h3><p>Separates effect magnitude from how confidently the evidence supports a conclusion.</p></div></div><div class="foot"><div>EvidenceOS v""" + __version__ + r""" · Research software alpha</div><div>Not a substitute for independent methodological or clinical judgement.</div></div></div></section>
</main>

<div id="studyDrawer" class="study-drawer" onclick="drawerBackdrop(event)">
  <aside class="drawer-panel">
    <div class="drawer-top"><div><div class="kicker">Study Workspace</div><h2 id="drawerTitle" style="margin:3px 0 0;font-size:24px;line-height:1.15"></h2></div><button class="close-btn" onclick="closeStudy()">×</button></div>
    <div id="drawerBody"></div>
  </aside>
</div>


<script>

const LANG_KEY='evidenceos_ui_language';
let EOS_LANG=localStorage.getItem(LANG_KEY)||((navigator.language||'').toLowerCase().startsWith('it')?'it':'en');
const EOS_IT={"Project": "Progetto", "Ask EvidenceOS": "Chiedi a EvidenceOS", "Analyse a study": "Analizza uno studio", "Evidence Synthesis": "Sintesi delle evidenze", "Evidence Graph": "Grafo delle evidenze", "Platform": "Piattaforma", "API docs": "Documentazione API", "Auditable evidence intelligence": "Intelligenza delle evidenze verificabile", "Evidence you can inspect,": "Evidenze che puoi ispezionare,", "not just summaries you can read.": "non solo riassunti da leggere.", "EvidenceOS reconstructs the path from scientific reports to structured evidence, preserving provenance and surfacing contradictions before they become conclusions.": "EvidenceOS ricostruisce il percorso dai report scientifici alle evidenze strutturate, preservando la provenienza e facendo emergere le contraddizioni prima che diventino conclusioni.", "Analyse a study →": "Analizza uno studio →", "Current public alpha": "Alpha pubblica attuale", "Source-linked": "Collegato alla fonte", "Every direct field carries provenance": "Ogni campo diretto conserva la provenienza", "Field-level": "A livello di campo", "Verified, derived or unresolved": "Verificato, derivato o non risolto", "Adversarial": "Avversariale", "Consistency alarms challenge outputs": "Gli allarmi di coerenza mettono alla prova gli output", "Persistent research workspace": "Workspace di ricerca persistente", "EvidenceOS Project.": "Progetto EvidenceOS.", "Keep the question, analysed studies, synthesis revisions, challenges and gaps together as one portable scientific project.": "Mantieni domanda, studi analizzati, revisioni della sintesi, challenge e gap insieme in un unico progetto scientifico portabile.", "Active project": "Progetto attivo", "Project name": "Nome del progetto", "New": "Nuovo", "Export JSON": "Esporta JSON", "Import": "Importa", "Project —": "Progetto —", "studies": "studi", "revisions": "revisioni", "Not saved yet": "Non ancora salvato", "Revision history": "Cronologia delle revisioni", "Refresh": "Aggiorna", "Browser persistence is the alpha storage layer. Export the project JSON for a portable backup; imported JSON is validated by the EvidenceOS backend before activation.": "La persistenza nel browser è il livello di archiviazione dell'alpha. Esporta il JSON del progetto per un backup portabile; i JSON importati vengono validati dal backend di EvidenceOS prima dell'attivazione.", "No revisions yet. Synthesis, challenge and gap-falsification events will appear here.": "Nessuna revisione. Gli eventi di sintesi, challenge e falsificazione dei gap compariranno qui.", "Project exported as JSON": "Progetto esportato come JSON", "Project imported and validated": "Progetto importato e validato", "New project ready.": "Nuovo progetto pronto.", "Define the question and add full-text studies.": "Definisci la domanda e aggiungi studi full text.", "No synthesis yet for this project.": "Nessuna sintesi disponibile per questo progetto.", "Untitled evidence project": "Progetto di evidenze senza titolo", "Evidence project 1": "Progetto di evidenze 1", "New evidence project": "Nuovo progetto di evidenze", "Question-first evidence discovery": "Ricerca delle evidenze guidata dalla domanda", "Ask EvidenceOS.": "Chiedi a EvidenceOS.", "Define the clinical or research question you actually want answered. In this public alpha, you confirm the PICO explicitly so the search logic remains transparent and reproducible.": "Definisci la domanda clinica o di ricerca a cui vuoi realmente rispondere. In questa alpha pubblica confermi esplicitamente il PICO, così la logica di ricerca resta trasparente e riproducibile.", "Research question": "Domanda di ricerca", "Population": "Popolazione", "Intervention": "Intervento", "Comparator": "Comparatore", "Outcomes": "Outcome", "Timepoint": "Tempo di follow-up", "Search scope": "Ampiezza della ricerca", "Quick": "Rapida", "Up to 10 records · rapid exploration": "Fino a 10 record · esplorazione rapida", "Standard": "Standard", "Up to 25 records · recommended": "Fino a 25 record · consigliata", "Broad": "Ampia", "Up to 50 records · wider exploration": "Fino a 50 record · esplorazione più ampia", "Controls how many PubMed records EvidenceOS initially examines. It does not represent evidence quality or certainty.": "Controlla quanti record PubMed EvidenceOS esamina inizialmente. Non rappresenta la qualità o la certezza delle evidenze.", "Load example": "Carica esempio", "Search PubMed": "Cerca su PubMed", "Searching": "Ricerca in corso", "Question, population, intervention and at least one outcome are required.": "Sono richiesti domanda, popolazione, intervento e almeno un outcome.", "Unique records": "Record unici", "Search strategies": "Strategie di ricerca", "Report links detected": "Collegamenti tra report rilevati", "Likely relevant": "Probabilmente rilevante", "Indirect": "Indiretto", "Uncertain": "Incerto", "Excluded": "Escluso", "All": "Tutti", "Interpretation boundary": "Limite interpretativo", "Eligibility and design labels are machine-assisted screening signals, not final systematic-review inclusion decisions. Full-text verification remains required.": "Le etichette di eleggibilità e design sono segnali di screening assistiti dalla macchina, non decisioni finali di inclusione in una revisione sistematica. È ancora necessaria la verifica del full text.", "Potential multiple-report links": "Possibili collegamenti tra più report", "No records in this category.": "Nessun record in questa categoria.", "Why this classification?": "Perché questa classificazione?", "No rationale available.": "Nessuna motivazione disponibile.", "Open Study Workspace →": "Apri Study Workspace →", "confidence": "confidenza", "uncertain design": "design incerto", "Live workspace": "Workspace operativo", "Turn a report into an auditable evidence record.": "Trasforma un report in un record di evidenza verificabile.", "Upload the full-text PDF. EvidenceOS extracts machine-readable text, reconstructs sample structure, maps results and flags inconsistencies. Unsupported fields remain unresolved.": "Carica il PDF full text. EvidenceOS estrae il testo leggibile dalla macchina, ricostruisce la struttura del campione, mappa i risultati e segnala le incoerenze. I campi non supportati restano non risolti.", "Full-text PDF": "PDF full text", "PDF-only study extraction": "Estrazione dello studio solo da PDF", "Report ID": "ID del report", "Study title": "Titolo dello studio", "Choose full-text PDF": "Seleziona PDF full text", "or drag and drop a PDF here · max 20 MB": "oppure trascina qui un PDF · max 20 MB", "Analyse full-text PDF": "Analizza PDF full text", "Analysing PDF": "Analisi PDF in corso", "Your full-text evidence record will appear here.": "Il record di evidenza del full text comparirà qui.", "EvidenceOS separates what is reported, what is derived and what remains uncertain.": "EvidenceOS distingue ciò che è riportato, ciò che è derivato e ciò che resta incerto.", "Universal Evidence Record": "Record universale di evidenza", "Sample sets": "Set di campione", "Results mapped": "Risultati mappati", "Consistency alarms": "Allarmi di coerenza", "Grounded sample fields": "Campi del campione supportati dalla fonte", "Study identity": "Identità dello studio", "Design": "Design", "Trial registration": "Registrazione del trial", "Sample structure": "Struttura del campione", "Total N": "N totale", "No sample structure could be verified.": "Non è stato possibile verificare la struttura del campione.", "Outcome results": "Risultati per outcome", "Outcome": "Outcome", "Instrument": "Strumento", "Effect measure": "Misura dell'effetto", "Estimate": "Stima", "95% CI lower": "Limite inferiore IC 95%", "95% CI upper": "Limite superiore IC 95%", "p value": "valore p", "Direction": "Direzione", "No result format was confidently mapped. Unsupported formats remain unresolved rather than guessed.": "Nessun formato di risultato è stato mappato con sufficiente sicurezza. I formati non supportati restano non risolti invece di essere dedotti.", "Epistemic alarms": "Allarmi epistemici", "No internal consistency alarm was triggered for the extracted fields.": "Nessun allarme di coerenza interna è stato attivato per i campi estratti.", "Raw record JSON": "JSON grezzo del record", "Derived:": "Derivato:", "Detected from uploaded full-text PDF by the EvidenceOS design router.": "Rilevato dal PDF full text caricato tramite il router di design di EvidenceOS.", "Add the study title.": "Aggiungi il titolo dello studio.", "Choose the full-text PDF.": "Seleziona il PDF full text.", "Only PDF files are supported.": "Sono supportati solo file PDF.", "EvidenceOS returned an invalid PDF analysis response.": "EvidenceOS ha restituito una risposta di analisi PDF non valida.", "Added to corpus": "Aggiunto al corpus", "Study Workspace": "Study Workspace", "Building appraisal scaffold…": "Costruzione dello schema di appraisal…", "Predicted design": "Design previsto", "Eligibility signal": "Segnale di eleggibilità", "Appraisal framework": "Framework di appraisal", "Appraisal readiness": "Prontezza per l'appraisal", "This measures information available for appraisal, not study quality.": "Misura le informazioni disponibili per l'appraisal, non la qualità dello studio.", "Signals observable from PubMed": "Segnali osservabili da PubMed", "Observed in title/abstract": "Osservato in titolo/abstract", "Not observed in abstract": "Non osservato nell'abstract", "Eligibility against your PICO": "Eleggibilità rispetto al tuo PICO", "No dimension-level rationale available.": "Nessuna motivazione disponibile a livello di dimensione.", "What EvidenceOS still needs": "Cosa serve ancora a EvidenceOS", "Abstract": "Abstract", "Continue to full-text analysis →": "Continua con l'analisi full text →", "Upload the full-text PDF in the Study Extraction workspace. RoB 2 will only become valid once outcome-specific full-text evidence is available.": "Carica il PDF full text nello Study Extraction workspace. RoB 2 diventa metodologicamente applicabile solo quando sono disponibili evidenze full text specifiche per outcome.", "Multi-study workspace": "Workspace multi-studio", "Evidence Synthesis Workspace.": "Workspace di sintesi delle evidenze.", "Save analysed full-text studies into a local evidence corpus, then inspect outcome patterns, contradictions, uncertainty and methodological coverage. The corpus belongs to the active EvidenceOS Project and is restored when you reopen that project in this browser.": "Salva gli studi full text analizzati in un corpus di evidenze, quindi esamina pattern degli outcome, contraddizioni, incertezza e copertura metodologica. Il corpus appartiene al progetto EvidenceOS attivo e viene ripristinato quando riapri il progetto in questo browser.", "saved studies": "studi salvati", "Stored locally in this browser": "Archiviati localmente in questo browser", "Clear corpus": "Svuota corpus", "Synthesize evidence": "Sintetizza evidenze", "Synthesizing": "Sintesi in corso", "No synthesis yet.": "Nessuna sintesi disponibile.", "Analyse and save at least one full-text PDF.": "Analizza e salva almeno un PDF full text.", "Save at least one analysed PDF first.": "Salva prima almeno un PDF analizzato.", "What does the evidence suggest?": "Cosa suggeriscono le evidenze?", "How resolved is the evidence?": "Quanto sono risolte le evidenze?", "Quantity": "Quantità", "Consistency": "Coerenza", "Methodology": "Metodologia", "Precision": "Precisione", "Directness": "Direttezza", "Outcome bodies": "Body of evidence per outcome", "Contradictions": "Contraddizioni", "No outcome-level evidence available.": "Nessuna evidenza disponibile a livello di outcome.", "No explicit directional contradiction detected.": "Nessuna contraddizione direzionale esplicita rilevata.", "What remains uncertain?": "Cosa resta incerto?", "No broad uncertainty automatically detected.": "Nessuna incertezza generale rilevata automaticamente.", "Falsifiable gap hypotheses": "Ipotesi di gap falsificabili", "EvidenceOS treats each apparent gap as a hypothesis and actively searches for counterevidence before calling it a research opportunity.": "EvidenceOS tratta ogni gap apparente come un'ipotesi e cerca attivamente controevidenza prima di definirlo un'opportunità di ricerca.", "No falsifiable gap hypothesis generated from this corpus.": "Nessuna ipotesi di gap falsificabile generata da questo corpus.", "Methodological support": "Supporto metodologico", "Challenge this conclusion →": "Metti alla prova questa conclusione →", "Try to prove the current interpretation wrong": "Prova a dimostrare che l'interpretazione corrente è errata", "Challenge this gap →": "Metti alla prova questo gap →", "Search PubMed for counterevidence": "Cerca controevidenza su PubMed", "Evidence for this outcome comes from a single analysed study.": "Le evidenze per questo outcome provengono da un singolo studio analizzato.", "The analysed evidence is heterogeneous; the dominant direction should be qualified.": "Le evidenze analizzate sono eterogenee; la direzione dominante deve essere qualificata.", "The available extracted results do not support a directional conclusion.": "I risultati estratti disponibili non supportano una conclusione direzionale.", "No outcome-level result was deterministically extracted from the stored PDFs.": "Nessun risultato a livello di outcome è stato estratto deterministicamente dai PDF salvati.", "Confidence intervals/precision information is largely unavailable in the extracted evidence.": "Le informazioni sugli intervalli di confidenza/precisione sono in gran parte non disponibili nelle evidenze estratte.", "Some outcomes contain inconsistent directional evidence that needs explanation.": "Alcuni outcome contengono evidenze direzionali incoerenti che richiedono spiegazione.", "Directness is intentionally not inferred until study-to-question PICO mapping is implemented.": "La direttezza non viene intenzionalmente inferita finché non sarà implementata la mappatura PICO studio-domanda.", "The analysed evidence shows a broadly consistent pattern.": "Le evidenze analizzate mostrano un pattern ampiamente coerente.", "The current body of evidence contains important contradictions.": "L'attuale body of evidence contiene contraddizioni importanti.", "The current evidence pattern is only partially resolved.": "Il pattern delle evidenze attuale è solo parzialmente risolto.", "EvidenceOS cannot yet form an outcome-level body of evidence.": "EvidenceOS non può ancora costruire un body of evidence a livello di outcome.", "This synthesis includes only PDFs explicitly analysed and saved in this browser workspace. It is not a systematic review, meta-analysis or GRADE assessment. EvidenceOS does not pool incompatible outcomes/designs and does not infer missing directness or publication-bias information.": "Questa sintesi include solo i PDF esplicitamente analizzati e salvati nel workspace. Non è una revisione sistematica, una meta-analisi o una valutazione GRADE. EvidenceOS non combina outcome/design incompatibili e non deduce informazioni mancanti su direttezza o publication bias.", "Gap falsification result": "Risultato della falsificazione del gap", "Refined statement": "Formulazione raffinata", "Records examined": "Record esaminati", "Direct counterevidence": "Controevidenza diretta", "Partial counterevidence": "Controevidenza parziale", "Anti-gap search provenance": "Provenienza della ricerca anti-gap", "PubMed query": "Query PubMed", "No records returned.": "Nessun record restituito.", "Trying to falsify this gap on PubMed…": "Tentativo di falsificare questo gap su PubMed…", "direct": "diretta", "partial": "parziale", "indirect": "indiretto", "rejected": "respinto", "refined": "raffinato", "not_falsified": "non falsificato", "unresolved": "non risolto", "Failure to retrieve a counterexample is not proof of a research gap. Search coverage, indexing, terminology and database scope remain sources of uncertainty.": "Il mancato reperimento di un controesempio non dimostra l'esistenza di un gap di ricerca. Copertura della ricerca, indicizzazione, terminologia e database restano fonti di incertezza.", "No PubMed records were returned by this anti-gap query. A negative search cannot establish that the literature is absent; broader terminology or databases may be needed.": "La query anti-gap non ha restituito record PubMed. Una ricerca negativa non può dimostrare l'assenza della letteratura; potrebbero servire termini più ampi o altri database.", "Challenge verdict": "Verdetto del challenge", "Revised conclusion": "Conclusione rivista", "PubMed records examined": "Record PubMed esaminati", "Potential contradictions": "Potenziali contraddizioni", "Higher-level challenges": "Challenge da evidenze di livello superiore", "External challenge provenance": "Provenienza del challenge esterno", "Adversarial PubMed query": "Query PubMed avversariale", "Challenging the conclusion against the stored corpus and PubMed…": "Messa alla prova della conclusione rispetto al corpus salvato e a PubMed…", "internal contradictory evidence": "evidenza interna contraddittoria", "thin evidence base": "base di evidenze limitata", "methodological uncertainty": "incertezza metodologica", "external contradictory evidence": "evidenza esterna contraddittoria", "higher level counterevidence": "controevidenza di livello superiore", "comparator trap": "trappola del comparatore", "timepoint and durability": "tempo di follow-up e durata", "potentially contradictory": "potenzialmente contraddittoria", "potentially supportive": "potenzialmente a supporto", "neutral or unclear": "neutra o non chiara", "evidence synthesis": "sintesi delle evidenze", "trial": "trial", "observational": "osservazionale", "other": "altro", "survived": "superata", "survived_with_qualification": "superata con qualificazioni", "materially_weakened": "sostanzialmente indebolita", "PubMed challenge records are screened from title/abstract signals only. They are potential counterevidence, not confirmed contradictions. A materially important record should be imported as full text and appraised before changing the final evidence conclusion.": "I record PubMed del challenge sono valutati solo tramite segnali da titolo/abstract. Rappresentano potenziale controevidenza, non contraddizioni confermate. Un record materialmente importante dovrebbe essere importato come full text e sottoposto ad appraisal prima di modificare la conclusione finale.", "No internal directional contradiction was detected in the stored body.": "Nessuna contraddizione direzionale interna rilevata nel body of evidence salvato.", "Methodological trust is insufficiently characterized across contributing studies.": "L'affidabilità metodologica è caratterizzata in modo insufficiente negli studi contribuenti.", "No directly relevant abstract-level contradictory signal was identified in this adversarial search.": "Nessun segnale contraddittorio direttamente rilevante a livello di abstract è stato identificato in questa ricerca avversariale.", "No directly relevant evidence-synthesis counter-signal was identified.": "Nessun controsegnale direttamente rilevante proveniente da sintesi delle evidenze è stato identificato.", "No clear alternative-comparator challenge was detected in the examined records.": "Nessun chiaro challenge legato a un comparatore alternativo è stato rilevato nei record esaminati.", "Durability could not be adequately challenged from titles/abstracts in this search.": "La durata dell'effetto non ha potuto essere adeguatamente messa alla prova usando titoli/abstract in questa ricerca.", "Add to evidence corpus →": "Aggiungi al corpus di evidenze →", "Checking full text…": "Verifica full text…", "Checking PMC availability and reuse status…": "Verifica disponibilità PMC e condizioni di riuso…", "Added automatically.": "Aggiunto automaticamente.", "PDF required.": "PDF richiesto.", "Choose PDF →": "Seleziona PDF →", "Retry intake": "Riprova importazione", "Challenge candidate added to corpus.": "Candidato del challenge aggiunto al corpus.", "EvidenceOS will recalculate the synthesis automatically.": "EvidenceOS ricalcolerà automaticamente la sintesi.", "Reusable PMC full text was imported automatically, appraised, and is ready to enter the evidence corpus.": "Il full text PMC riutilizzabile è stato importato automaticamente, sottoposto ad appraisal ed è pronto per entrare nel corpus di evidenze.", "No reusable PMC full text was identified automatically. Upload the full-text PDF to continue.": "Non è stato identificato automaticamente un full text PMC riutilizzabile. Carica il PDF full text per continuare.", "The article is in PMC, but EvidenceOS did not verify a sufficiently permissive commercial-use license for automatic ingestion. Upload your full-text PDF instead.": "L'articolo è presente in PMC, ma EvidenceOS non ha verificato una licenza sufficientemente permissiva per l'uso commerciale e l'importazione automatica. Carica invece il tuo PDF full text.", "How much can we trust this study?": "Quanto possiamo fidarci di questo studio?", "Detected design:": "Design rilevato:", "Interpretation limits": "Limiti interpretativi", "Why this judgement?": "Perché questo giudizio?", "Preliminary RoB 2 assistance available": "Assistenza preliminare RoB 2 disponibile", "Outcome-specific randomized-trial appraisal": "Appraisal del trial randomizzato specifico per outcome", "Non-randomized intervention appraisal": "Appraisal dello studio di intervento non randomizzato", "Cohort study appraisal": "Appraisal dello studio di coorte", "Case-control study appraisal": "Appraisal dello studio caso-controllo", "Cross-sectional study appraisal": "Appraisal dello studio trasversale", "Prevalence study appraisal": "Appraisal dello studio di prevalenza", "Diagnostic accuracy appraisal": "Appraisal dello studio di accuratezza diagnostica", "Qualitative study appraisal": "Appraisal dello studio qualitativo", "Case series appraisal": "Appraisal della serie di casi", "Case report appraisal": "Appraisal del case report", "Prediction model appraisal": "Appraisal del modello predittivo", "Economic evaluation appraisal": "Appraisal della valutazione economica", "Systematic review appraisal": "Appraisal della revisione sistematica", "Scoping review appraisal": "Appraisal della scoping review", "Clinical guideline appraisal": "Appraisal della linea guida clinica", "Protocol detected": "Protocollo rilevato", "Study design requires confirmation": "Il design dello studio richiede conferma", "Full-text extraction succeeded; appraisal was not completed": "Estrazione del full text completata; appraisal non completato", "EvidenceOS RCT bias engine (RoB 2-aligned concepts)": "Motore EvidenceOS per il bias negli RCT (concetti allineati a RoB 2)", "EvidenceOS non-randomized intervention bias engine (ROBINS-I-oriented concepts)": "Motore EvidenceOS per il bias negli studi di intervento non randomizzati (concetti orientati a ROBINS-I)", "EvidenceOS cohort risk-of-bias engine (JBI-oriented constructs)": "Motore EvidenceOS per il rischio di bias negli studi di coorte (costrutti orientati JBI)", "EvidenceOS case-control bias engine (JBI-oriented constructs)": "Motore EvidenceOS per il bias negli studi caso-controllo (costrutti orientati JBI)", "EvidenceOS analytical cross-sectional bias engine (revised JBI-oriented constructs)": "Motore EvidenceOS per il bias negli studi trasversali analitici (costrutti JBI revisionati)", "EvidenceOS prevalence-study appraisal (JBI-oriented constructs)": "Appraisal EvidenceOS degli studi di prevalenza (costrutti orientati JBI)", "EvidenceOS diagnostic accuracy engine (QUADAS-3-oriented concepts)": "Motore EvidenceOS per l'accuratezza diagnostica (concetti orientati a QUADAS-3)", "EvidenceOS qualitative appraisal (JBI/CASP-oriented constructs)": "Appraisal qualitativo EvidenceOS (costrutti orientati JBI/CASP)", "EvidenceOS case-series appraisal (JBI-oriented constructs)": "Appraisal EvidenceOS delle serie di casi (costrutti orientati JBI)", "EvidenceOS case-report appraisal (JBI-oriented constructs)": "Appraisal EvidenceOS dei case report (costrutti orientati JBI)", "EvidenceOS prediction-model appraisal (PROBAST-oriented concepts)": "Appraisal EvidenceOS dei modelli predittivi (concetti orientati a PROBAST)", "EvidenceOS economic-evaluation appraisal": "Appraisal EvidenceOS delle valutazioni economiche", "EvidenceOS systematic-review appraisal (AMSTAR 2-oriented critical domains)": "Appraisal EvidenceOS delle revisioni sistematiche (domini critici orientati ad AMSTAR 2)", "EvidenceOS scoping-review methods appraisal": "Appraisal EvidenceOS dei metodi delle scoping review", "EvidenceOS guideline appraisal (AGREE-style domains)": "Appraisal EvidenceOS delle linee guida (domini in stile AGREE)", "EvidenceOS protocol appraisal": "Appraisal EvidenceOS dei protocolli", "EvidenceOS generic appraisal scaffold": "Schema generico di appraisal EvidenceOS", "human_verification_required": "richiede verifica umana", "substantial_information_available": "informazioni sostanziali disponibili", "outcome_specific": "specifico per outcome", "not_an_effect_estimate": "non è una stima di effetto", "appraisal_error": "errore di appraisal", "not_applicable": "non applicabile", "signal_present": "segnale presente", "Confounding": "Confondimento", "Classification of intervention": "Classificazione dell'intervento", "Selection into the study": "Selezione nello studio", "Deviations from intended intervention": "Deviazioni dall'intervento previsto", "Missing data": "Dati mancanti", "Outcome measurement": "Misurazione dell'outcome", "Selection of reported result": "Selezione del risultato riportato", "Selection and group comparability": "Selezione e comparabilità dei gruppi", "Exposure measurement": "Misurazione dell'esposizione", "Outcome at baseline / temporality": "Outcome al baseline / temporalità", "Follow-up and missingness": "Follow-up e dati mancanti", "Outcome measurement and analysis": "Misurazione dell'outcome e analisi", "Case definition": "Definizione dei casi", "Control selection": "Selezione dei controlli", "Exposure ascertainment": "Accertamento dell'esposizione", "Comparable ascertainment": "Accertamento comparabile", "Analysis": "Analisi", "Sampling frame and recruitment": "Frame di campionamento e reclutamento", "Eligibility criteria": "Criteri di eleggibilità", "Statistical analysis": "Analisi statistica", "Representative sampling frame": "Frame di campionamento rappresentativo", "Sampling method": "Metodo di campionamento", "Adequate sample planning": "Adeguata pianificazione della numerosità", "Condition measurement": "Misurazione della condizione", "Response / coverage": "Risposta / copertura", "Prevalence estimation": "Stima della prevalenza", "Participants": "Partecipanti", "Index test": "Test indice", "Target condition": "Condizione target", "Prospective protocol": "Protocollo prospettico", "Comprehensive search": "Ricerca esaustiva", "Duplicate review processes": "Processi di revisione in duplicato", "Risk-of-bias assessment": "Valutazione del rischio di bias", "Publication bias": "Bias di pubblicazione", "Protocol and a priori methods": "Protocollo e metodi a priori", "Search comprehensiveness": "Completezza della ricerca", "Duplicate study processes": "Processi in duplicato", "Risk-of-bias methods": "Metodi per il rischio di bias", "Synthesis methods": "Metodi di sintesi", "Heterogeneity": "Eterogeneità", "Small-study/publication bias": "Bias da piccoli studi/pubblicazione", "Conflicts and funding": "Conflitti e finanziamenti", "Congruity of methodology and question": "Coerenza tra metodologia e domanda", "Sampling and recruitment": "Campionamento e reclutamento", "Data collection": "Raccolta dati", "Researcher reflexivity": "Riflessività del ricercatore", "Grounding of findings": "Radicamento dei risultati nei dati", "Ethics": "Etica", "Clear inclusion criteria": "Criteri di inclusione chiari", "Reliable condition measurement": "Misurazione affidabile della condizione", "Consecutive/complete inclusion": "Inclusione consecutiva/completa", "Participant characteristics": "Caratteristiche dei partecipanti", "Clinical information/outcomes": "Informazioni cliniche/outcome", "Patient description": "Descrizione del paziente", "History/timeline": "Anamnesi/timeline", "Diagnostic assessment": "Valutazione diagnostica", "Follow-up/outcome": "Follow-up/outcome", "Predictors": "Predittori", "Perspective": "Prospettiva", "Comparators": "Comparatori", "Costs and outcomes": "Costi e outcome", "Time horizon / discounting": "Orizzonte temporale / attualizzazione", "Incremental analysis": "Analisi incrementale", "Uncertainty": "Incertezza", "Scope and purpose": "Ambito e finalità", "Stakeholder involvement": "Coinvolgimento degli stakeholder", "Rigour of development": "Rigore dello sviluppo", "Clarity": "Chiarezza", "Applicability": "Applicabilità", "Editorial independence": "Indipendenza editoriale", "Clear objectives": "Obiettivi chiari", "Prespecified methods": "Metodi prespecificati", "Registration": "Registrazione", "verified": "verificato", "derived": "derivato", "unverified": "non verificato", "ambiguous": "ambiguo", "conflicting": "in conflitto", "not_reported": "non riportato", "not reported": "non riportato", "observed": "osservato", "include": "includere", "exclude": "escluso", "uncertain": "incerto", "low": "basso", "some_concerns": "alcune criticità", "high": "alto", "minor": "minore", "material": "materiale", "critical": "critico", "none": "nessuno", "quantity": "quantità", "precision": "precisione", "consistency": "coerenza", "temporal": "temporale", "comparator": "comparatore", "replication": "replicazione", "limited": "limitata", "moderate": "moderata", "substantial": "sostanziale", "broadly_consistent": "ampiamente coerente", "partially_consistent": "parzialmente coerente", "concerns": "criticità", "not_assessable": "non valutabile", "relatively_well_characterized": "relativamente ben caratterizzato", "partially_characterized": "parzialmente caratterizzato", "insufficiently_characterized": "caratterizzato in modo insufficiente", "mostly_available": "prevalentemente disponibile", "partially_available": "parzialmente disponibile", "mostly_unavailable": "prevalentemente non disponibile", "not_yet_assessed": "non ancora valutata", "more_resolved": "più risolta", "partially_resolved": "parzialmente risolta", "substantially_uncertain": "sostanzialmente incerta", "consistent": "coerente", "mostly_consistent": "prevalentemente coerente", "mixed": "mista", "favours_intervention": "favorisce l'intervento", "favours_comparator": "favorisce il comparatore", "no_clear_difference": "nessuna differenza chiara", "randomized_controlled_trial": "trial randomizzato controllato", "nonrandomized_intervention": "studio di intervento non randomizzato", "cohort": "studio di coorte", "case_control": "studio caso-controllo", "cross_sectional": "studio trasversale", "prevalence": "studio di prevalenza", "diagnostic_accuracy": "studio di accuratezza diagnostica", "qualitative": "studio qualitativo", "case_series": "serie di casi", "case_report": "case report", "prediction_model": "modello predittivo", "economic_evaluation": "valutazione economica", "systematic_review": "revisione sistematica", "meta_analysis": "meta-analisi", "network_meta_analysis": "network meta-analysis", "scoping_review": "scoping review", "guideline": "linea guida", "protocol": "protocollo", "Epistemic provenance map": "Mappa della provenienza epistemica", "Evidence Graph.": "Grafo delle evidenze.", "Inspect the current project as a graph: research question → full-text studies → outcome bodies → challenges and gap hypotheses. The graph represents relationships, not causal certainty.": "Esamina il progetto corrente come grafo: domanda di ricerca → studi full text → body of evidence per outcome → challenge e ipotesi di gap. Il grafo rappresenta relazioni, non certezza causale.", "Question": "Domanda", "Study": "Studio", "Outcome body": "Body of evidence", "Challenge": "Challenge", "Gap hypothesis": "Ipotesi di gap", "Run or restore an Evidence Synthesis to build the graph.": "Esegui o ripristina una sintesi delle evidenze per costruire il grafo.", "Add analysed studies to this project to build the graph.": "Aggiungi studi analizzati a questo progetto per costruire il grafo.", "research question": "domanda di ricerca", "Evidence intelligence platform": "Piattaforma di evidence intelligence", "Beyond extraction.": "Oltre l'estrazione.", "The broader EvidenceOS architecture is being validated as separate modules rather than presented as one opaque AI answer.": "L'architettura più ampia di EvidenceOS viene validata come insieme di moduli separati, invece di essere presentata come un'unica risposta AI opaca.", "Live alpha": "Alpha attiva", "Record-level appraisal readiness, full-text handoff, sample flow, arms, outcomes, timepoints, effect estimates and provenance.": "Prontezza per l'appraisal a livello di record, passaggio al full text, flusso del campione, bracci, outcome, timepoint, stime dell'effetto e provenienza.", "Experimental": "Sperimentale", "Critical Appraisal": "Appraisal critico", "Outcome-specific methodological signals and RoB 2 assistance with source-linked rationale.": "Segnali metodologici specifici per outcome e assistenza RoB 2 con motivazione collegata alla fonte.", "Project + Evidence Graph": "Progetto + Grafo delle evidenze", "Persists question, studies, synthesis revisions, challenge history and gap hypotheses as one exportable project with an inspectable evidence graph.": "Conserva domanda, studi, revisioni della sintesi, cronologia dei challenge e ipotesi di gap in un unico progetto esportabile con grafo delle evidenze ispezionabile.", "Challenge Engine": "Challenge Engine", "Actively looks for comparator traps, contradictory results and quality asymmetries.": "Cerca attivamente trappole del comparatore, risultati contraddittori e asimmetrie di qualità.", "Gap Falsification": "Falsificazione dei gap", "Turns apparent gaps into hypotheses and searches PubMed for counterevidence before calling them research opportunities.": "Trasforma i gap apparenti in ipotesi e cerca controevidenza su PubMed prima di definirli opportunità di ricerca.", "In validation": "In validazione", "Certainty Calibration": "Calibrazione della certezza", "Separates effect magnitude from how confidently the evidence supports a conclusion.": "Separa la magnitudine dell'effetto dal grado di fiducia con cui le evidenze supportano una conclusione.", "Not a substitute for independent methodological or clinical judgement.": "Non sostituisce un giudizio metodologico o clinico indipendente.", "Clear all locally saved EvidenceOS studies from this browser?": "Eliminare tutti gli studi EvidenceOS salvati localmente in questo browser?", "Browser storage is full. Export this project as JSON before adding more evidence.": "Lo spazio di archiviazione del browser è pieno. Esporta il progetto come JSON prima di aggiungere altre evidenze.", "Could not import EvidenceOS project:": "Impossibile importare il progetto EvidenceOS:", "Project validation failed": "Validazione del progetto non riuscita", "EvidenceOS received a non-JSON response from the backend.": "EvidenceOS ha ricevuto dal backend una risposta non JSON.", "Appropriate random-sequence method reported.": "Metodo appropriato di generazione della sequenza casuale riportato.", "No clear random-sequence method identified.": "Nessun metodo chiaro di generazione della sequenza casuale identificato.", "Allocation-concealment signal identified.": "Segnale di occultamento dell'allocazione identificato.", "No clear allocation-concealment information identified.": "Nessuna informazione chiara sull'occultamento dell'allocazione identificata.", "Potential baseline imbalance explicitly reported.": "Potenziale squilibrio al baseline riportato esplicitamente.", "No explicit baseline-imbalance problem identified.": "Nessun problema esplicito di squilibrio al baseline identificato.", "Participants reported as blinded/masked.": "Partecipanti riportati come ciechi/mascherati.", "Participant awareness not clearly established.": "Consapevolezza dei partecipanti rispetto all'allocazione non chiaramente stabilita.", "Personnel reported as blinded.": "Personale riportato come cieco.", "Personnel awareness not clearly established.": "Consapevolezza del personale rispetto all'allocazione non chiaramente stabilita.", "Potential intervention deviation reported.": "Potenziale deviazione dall'intervento riportata.", "No clear trial-context deviation information identified.": "Nessuna informazione chiara su deviazioni legate al contesto del trial identificata.", "Requires contextual judgement beyond deterministic extraction.": "Richiede un giudizio contestuale oltre l'estrazione deterministica.", "Intention-to-treat analysis reported.": "Analisi intention-to-treat riportata.", "Appropriateness of analysis cannot be established from extracted signals.": "L'appropriatezza dell'analisi non può essere stabilita dai segnali estratti.", "Missingness terminology found; proportion/completeness requires result-level analysis.": "Rilevata terminologia relativa ai dati mancanti; proporzione e completezza richiedono un'analisi a livello di risultato.", "Outcome-data completeness not clearly established.": "Completezza dei dati di outcome non chiaramente stabilita.", "Requires result-level judgement about missingness.": "Richiede un giudizio a livello di risultato sui dati mancanti.", "Cannot be inferred safely without additional evidence.": "Non può essere inferito in modo sicuro senza evidenze aggiuntive.", "Validated measurement method explicitly reported.": "Metodo di misurazione validato riportato esplicitamente.", "Appropriateness of measurement method not established.": "Appropriatezza del metodo di misurazione non stabilita.", "No deterministic signal implemented for differential measurement.": "Nessun segnale deterministico implementato per la misurazione differenziale.", "Outcome assessor reported as blinded.": "Valutatore dell'outcome riportato come cieco.", "Outcome-assessor awareness not established.": "Consapevolezza del valutatore dell'outcome non stabilita.", "Requires outcome-specific contextual judgement.": "Richiede un giudizio contestuale specifico per outcome.", "Prospective analysis/protocol signal identified.": "Segnale di analisi/protocollo prospettico identificato.", "Prespecification cannot be established.": "La prespecificazione non può essere stabilita.", "Requires comparison with protocol/registry and outcome definitions.": "Richiede il confronto con protocollo/registro e definizioni degli outcome.", "Requires comparison with planned analyses.": "Richiede il confronto con le analisi pianificate.", "Confounding/adjustment strategy detected.": "Strategia di controllo del confondimento/aggiustamento rilevata.", "Important confounders and adequacy of control require verification.": "I confondenti importanti e l'adeguatezza del controllo richiedono verifica.", "Intervention classification information detected.": "Informazioni sulla classificazione dell'intervento rilevate.", "Misclassification of intervention remains unresolved.": "La misclassificazione dell'intervento resta non risolta.", "Selection/eligibility information detected.": "Informazioni su selezione/eleggibilità rilevate.", "Selection mechanisms require verification.": "I meccanismi di selezione richiedono verifica.", "Intervention-deviation/adherence information detected.": "Informazioni su deviazioni dall'intervento/aderenza rilevate.", "Bias from deviations remains unresolved.": "Il bias dovuto alle deviazioni resta non risolto.", "Missing-data information detected.": "Informazioni sui dati mancanti rilevate.", "Amount, mechanism and handling of missingness require verification.": "Quantità, meccanismo e gestione dei dati mancanti richiedono verifica.", "Outcome-measurement safeguard detected.": "Salvaguardia relativa alla misurazione dell'outcome rilevata.", "Differential or biased measurement remains unresolved.": "La misurazione differenziale o distorta resta non risolta.", "Prespecification signal detected.": "Segnale di prespecificazione rilevato.", "Selective reporting cannot be excluded automatically.": "Il reporting selettivo non può essere escluso automaticamente.", "A formal ROBINS-I assessment requires review-specific specification of the target trial and important confounders.": "Una valutazione formale ROBINS-I richiede la specificazione, per la revisione, del target trial e dei confondenti importanti.", "This output is not an official ROBINS-I judgement.": "Questo output non costituisce un giudizio ROBINS-I ufficiale.", "Selection/comparator information detected.": "Informazioni su selezione/comparatore rilevate.", "Selection and comparability require verification.": "Selezione e comparabilità richiedono verifica.", "Exposure measurement information detected.": "Informazioni sulla misurazione dell'esposizione rilevate.", "Exposure validity/reliability unresolved.": "Validità/affidabilità della misurazione dell'esposizione non risolta.", "Confounder handling detected.": "Gestione dei confondenti rilevata.", "Residual/unmeasured confounding unresolved.": "Confondimento residuo/non misurato non risolto.", "Temporal information detected.": "Informazioni temporali rilevate.", "Temporality requires verification.": "La temporalità richiede verifica.", "Follow-up information detected.": "Informazioni sul follow-up rilevate.", "Completeness and differential loss unresolved.": "Completezza e perdite differenziali non risolte.", "Outcome/analysis signal detected.": "Segnale relativo a outcome/analisi rilevato.", "Outcome ascertainment and model adequacy unresolved.": "Accertamento dell'outcome e adeguatezza del modello non risolti.", "Case-definition signal detected.": "Segnale sulla definizione dei casi rilevato.", "Validity of case definition unresolved.": "Validità della definizione dei casi non risolta.", "Control-selection information detected.": "Informazioni sulla selezione dei controlli rilevate.", "Source-population comparability unresolved.": "Comparabilità con la popolazione sorgente non risolta.", "Exposure-ascertainment signal detected.": "Segnale sull'accertamento dell'esposizione rilevato.", "Recall/differential ascertainment unresolved.": "Bias di richiamo/accertamento differenziale non risolto.", "Comparable/blinded ascertainment signal detected.": "Segnale di accertamento comparabile/in cieco rilevato.", "Differential measurement unresolved.": "Misurazione differenziale non risolta.", "Matching/adjustment signal detected.": "Segnale di matching/aggiustamento rilevato.", "Residual confounding unresolved.": "Confondimento residuo non risolto.", "Case-control analysis signal detected.": "Segnale di analisi caso-controllo rilevato.", "Analysis specification and reporting require verification.": "Specificazione dell'analisi e reporting richiedono verifica.", "Sampling strategy detected.": "Strategia di campionamento rilevata.", "Representativeness/selection bias unresolved.": "Rappresentatività/bias di selezione non risolti.", "Eligibility criteria detected.": "Criteri di eleggibilità rilevati.", "Eligibility definition unresolved.": "Definizione dell'eleggibilità non risolta.", "Measurement-quality signal detected.": "Segnale sulla qualità della misurazione rilevato.", "Exposure measurement validity unresolved.": "Validità della misurazione dell'esposizione non risolta.", "Outcome-definition signal detected.": "Segnale sulla definizione dell'outcome rilevato.", "Outcome ascertainment unresolved.": "Accertamento dell'outcome non risolto.", "Confounding strategy detected.": "Strategia per il confondimento rilevata.", "Statistical-analysis signal detected.": "Segnale di analisi statistica rilevato.", "Model assumptions/precision require verification.": "Assunzioni del modello/precisione richiedono verifica.", "Population/sampling-frame signal detected.": "Segnale su popolazione/frame di campionamento rilevato.", "Representativeness unresolved.": "Rappresentatività non risolta.", "Probability-sampling signal detected.": "Segnale di campionamento probabilistico rilevato.", "Sampling bias unresolved.": "Bias di campionamento non risolto.", "Sample-size planning detected.": "Pianificazione della numerosità campionaria rilevata.", "Precision planning unresolved.": "Pianificazione della precisione non risolta.", "Condition-measurement signal detected.": "Segnale sulla misurazione della condizione rilevato.", "Measurement validity unresolved.": "Validità della misurazione non risolta.", "Response information detected.": "Informazioni sulla risposta rilevate.", "Non-response bias unresolved.": "Bias da non risposta non risolto.", "Prevalence precision signal detected.": "Segnale sulla precisione della prevalenza rilevato.", "Estimation/weighting details unresolved.": "Dettagli di stima/ponderazione non risolti.", "Participant-selection signal detected.": "Segnale sulla selezione dei partecipanti rilevato.", "Participant selection/applicability unresolved.": "Selezione dei partecipanti/applicabilità non risolte.", "Index-test methods detected.": "Metodi del test indice rilevati.", "Threshold/interpretation bias unresolved.": "Bias legato a soglia/interpretazione non risolto.", "Target-condition/reference-standard signal detected.": "Segnale su condizione target/standard di riferimento rilevato.", "Target-condition classification unresolved.": "Classificazione della condizione target non risolta.", "Accuracy-analysis signal detected.": "Segnale di analisi dell'accuratezza rilevato.", "Estimate-specific exclusions/analysis choices unresolved.": "Esclusioni/scelte analitiche specifiche per la stima non risolte.", "A formal QUADAS-3 appraisal must be anchored to a synthesis question, ideal test accuracy trial and selected accuracy estimate.": "Un appraisal formale QUADAS-3 deve essere ancorato a una domanda di sintesi, a un ideal test accuracy trial e alla stima di accuratezza selezionata.", "The current QUADAS-3 framework is estimate-level. EvidenceOS therefore treats these as preliminary estimate-relevant signals, not a formal QUADAS-3 assessment.": "L'attuale framework QUADAS-3 opera a livello di stima. EvidenceOS tratta quindi questi elementi come segnali preliminari rilevanti per la stima, non come una valutazione QUADAS-3 formale.", "Methodological approach identified.": "Approccio metodologico identificato.", "Methodological congruity unresolved.": "Coerenza metodologica non risolta.", "Sampling adequacy unresolved.": "Adeguatezza del campionamento non risolta.", "Data-collection method detected.": "Metodo di raccolta dati rilevato.", "Depth/appropriateness of collection unresolved.": "Profondità/appropriatezza della raccolta dati non risolte.", "Reflexivity signal detected.": "Segnale di riflessività rilevato.", "Researcher influence/relationship unresolved.": "Influenza/relazione del ricercatore non risolta.", "Analytic method detected.": "Metodo analitico rilevato.", "Analytic rigor and auditability unresolved.": "Rigore analitico e verificabilità non risolti.", "Participant-data grounding signal detected.": "Segnale di radicamento nei dati dei partecipanti rilevato.", "Data-to-theme grounding unresolved.": "Radicamento dei temi nei dati non risolto.", "Ethics/consent signal detected.": "Segnale relativo a etica/consenso rilevato.", "Ethical conduct unresolved.": "Condotta etica non risolta.", "Protocol/registration detected.": "Protocollo/registrazione rilevato.", "Prospective protocol not verified.": "Protocollo prospettico non verificato.", "Multiple databases detected.": "Più database rilevati.", "Search coverage unresolved.": "Copertura della ricerca non risolta.", "Duplicate/independent process detected.": "Processo in duplicato/indipendente rilevato.", "Study selection/extraction duplication unresolved.": "Duplicazione di selezione/estrazione degli studi non risolta.", "Risk-of-bias appraisal detected.": "Appraisal del rischio di bias rilevato.", "Appropriateness of appraisal unresolved.": "Appropriatezza dell'appraisal non risolta.", "Synthesis-method signal detected.": "Segnale sui metodi di sintesi rilevato.", "Suitability of synthesis assumptions unresolved.": "Adeguatezza delle assunzioni di sintesi non risolta.", "Heterogeneity assessment detected.": "Valutazione dell'eterogeneità rilevata.", "Exploration/interpretation of heterogeneity unresolved.": "Esplorazione/interpretazione dell'eterogeneità non risolta.", "Small-study/publication-bias assessment detected.": "Valutazione del bias da piccoli studi/pubblicazione rilevata.", "Publication bias unresolved.": "Bias di pubblicazione non risolto.", "Funding/conflict information detected.": "Informazioni su finanziamenti/conflitti rilevate.", "Influence of conflicts/funding unresolved.": "Influenza di conflitti/finanziamenti non risolta.", "AMSTAR 2 is not a numerical score; EvidenceOS similarly reports domain signals and critical weaknesses rather than summing points.": "AMSTAR 2 non è un punteggio numerico; allo stesso modo EvidenceOS riporta segnali per dominio e debolezze critiche invece di sommare punti.", "This is not an official AMSTAR 2 assessment unless separately licensed/validated.": "Questa non è una valutazione AMSTAR 2 ufficiale salvo licenza/validazione separata.", "Clear inclusion criteria detected.": "Criteri di inclusione chiari rilevati.", "Case inclusion criteria unresolved.": "Criteri di inclusione dei casi non risolti.", "Condition ascertainment signal detected.": "Segnale sull'accertamento della condizione rilevato.", "Reliability of diagnosis unresolved.": "Affidabilità della diagnosi non risolta.", "Consecutive/complete inclusion signal detected.": "Segnale di inclusione consecutiva/completa rilevato.", "Selection of cases unresolved.": "Selezione dei casi non risolta.", "Participant description detected.": "Descrizione dei partecipanti rilevata.", "Completeness of participant description unresolved.": "Completezza della descrizione dei partecipanti non risolta.", "Clinical course/outcome signal detected.": "Segnale sul decorso clinico/outcome rilevato.", "Completeness of clinical reporting unresolved.": "Completezza del reporting clinico non risolta.", "Patient-description signal detected.": "Segnale sulla descrizione del paziente rilevato.", "Patient characteristics unresolved.": "Caratteristiche del paziente non risolte.", "History/timeline signal detected.": "Segnale su anamnesi/timeline rilevato.", "Clinical timeline unresolved.": "Timeline clinica non risolta.", "Diagnostic work-up signal detected.": "Segnale sul work-up diagnostico rilevato.", "Diagnostic reasoning unresolved.": "Ragionamento diagnostico non risolto.", "Intervention information detected.": "Informazioni sull'intervento rilevate.", "Intervention detail unresolved.": "Dettagli dell'intervento non risolti.", "Follow-up/outcome signal detected.": "Segnale su follow-up/outcome rilevato.", "Outcome completeness unresolved.": "Completezza dell'outcome non risolta.", "Predictor-definition signal detected.": "Segnale sulla definizione dei predittori rilevato.", "Predictor assessment/blinding unresolved.": "Valutazione dei predittori/blinding non risolti.", "Model-performance analysis detected.": "Analisi delle performance del modello rilevata.", "Overfitting, sample size and validation require verification.": "Overfitting, numerosità campionaria e validazione richiedono verifica.", "Formal PROBAST/PROBAST+AI use may require review-specific signalling judgements.": "L'uso formale di PROBAST/PROBAST+AI può richiedere giudizi sulle signalling questions specifici per la revisione.", "Economic perspective detected.": "Prospettiva economica rilevata.", "Perspective unresolved.": "Prospettiva non risolta.", "Comparator signal detected.": "Segnale sul comparatore rilevato.", "Relevance/completeness of alternatives unresolved.": "Rilevanza/completezza delle alternative non risolta.", "Cost/outcome measurement detected.": "Misurazione di costi/outcome rilevata.", "Valuation validity unresolved.": "Validità della valorizzazione non risolta.", "Time/discounting signal detected.": "Segnale su tempo/attualizzazione rilevato.", "Appropriateness unresolved.": "Appropriatezza non risolta.", "Incremental analysis detected.": "Analisi incrementale rilevata.", "Incremental-method validity unresolved.": "Validità del metodo incrementale non risolta.", "Uncertainty analysis detected.": "Analisi dell'incertezza rilevata.", "Structural/parameter uncertainty unresolved.": "Incertezza strutturale/dei parametri non risolta.", "Scope/purpose signal detected.": "Segnale su ambito/finalità rilevato.", "Scope clarity unresolved.": "Chiarezza dell'ambito non risolta.", "Stakeholder signal detected.": "Segnale sugli stakeholder rilevato.", "Stakeholder breadth unresolved.": "Ampiezza del coinvolgimento degli stakeholder non risolta.", "Evidence-development process detected.": "Processo di sviluppo delle evidenze rilevato.", "Rigour/updates unresolved.": "Rigore/aggiornamenti non risolti.", "Recommendations detected.": "Raccomandazioni rilevate.", "Specificity/actionability unresolved.": "Specificità/azionabilità non risolte.", "Implementation/applicability signal detected.": "Segnale su implementazione/applicabilità rilevato.", "Applicability planning unresolved.": "Pianificazione dell'applicabilità non risolta.", "Conflict/funding information detected.": "Informazioni su conflitti/finanziamenti rilevate.", "Editorial independence unresolved.": "Indipendenza editoriale non risolta.", "Objectives detected.": "Obiettivi rilevati.", "Objectives unresolved.": "Obiettivi non risolti.", "Methods signal detected.": "Segnale sui metodi rilevato.", "Method completeness unresolved.": "Completezza dei metodi non risolta.", "Registration detected.": "Registrazione rilevata.", "Registration not verified.": "Registrazione non verificata.", "Scoping reviews are evaluated for transparent question, search, selection, charting and synthesis methods rather than intervention-effect risk of bias.": "Le scoping review vengono valutate per trasparenza di domanda, ricerca, selezione, charting e metodi di sintesi, piuttosto che per il rischio di bias dell'effetto dell'intervento.", "Bibliographic search detected.": "Ricerca bibliografica rilevata.", "Search comprehensiveness unresolved.": "Completezza della ricerca non risolta.", "Independent selection signal detected.": "Segnale di selezione indipendente rilevato.", "Selection process unresolved.": "Processo di selezione non risolto.", "Charting/extraction signal detected.": "Segnale di charting/estrazione rilevato.", "Charting reliability unresolved.": "Affidabilità del charting non risolta.", "Synthesis method detected.": "Metodo di sintesi rilevato.", "Synthesis transparency unresolved.": "Trasparenza della sintesi non risolta.", "Protocols are assessed for planned methodological safeguards, not completed effect estimates.": "I protocolli vengono valutati per le salvaguardie metodologiche pianificate, non per stime di effetto completate.", "EvidenceOS could not route this report confidently to a design-specific appraisal engine.": "EvidenceOS non ha potuto indirizzare con sufficiente sicurezza questo report verso un motore di appraisal specifico per design.", "Confirm the study design before interpreting methodological trustworthiness.": "Conferma il design dello studio prima di interpretarne l'affidabilità metodologica.", "EvidenceOS extracted the PDF successfully, but the methodological appraisal layer encountered an internal error. The evidence record is still available and no trust judgement has been invented.": "EvidenceOS ha estratto correttamente il PDF, ma il livello di appraisal metodologico ha riscontrato un errore interno. Il record di evidenza resta disponibile e non è stato inventato alcun giudizio di affidabilità.", "EvidenceOS applies its own deterministic implementation of core randomized-trial bias concepts. This commercial software does not claim to reproduce the official RoB 2 instrument. Human verification remains required.": "EvidenceOS applica una propria implementazione deterministica dei principali concetti di bias nei trial randomizzati. Questo software commerciale non dichiara di riprodurre lo strumento RoB 2 ufficiale. Resta necessaria la verifica umana.", "At most three deterministically mapped outcomes are assessed in one synchronous request.": "In una singola richiesta sincrona vengono valutati al massimo tre outcome mappati deterministicamente.", "Formal use of third-party proprietary/licensed tools may require separate permission.": "L'uso formale di strumenti di terze parti proprietari o soggetti a licenza può richiedere un'autorizzazione separata.", "The engine evaluates major bias mechanisms relevant to non-randomized intervention studies without reproducing the official ROBINS-I instrument.": "Il motore valuta i principali meccanismi di bias rilevanti per gli studi di intervento non randomizzati senza riprodurre lo strumento ROBINS-I ufficiale.", "Full-text signals are organised around selection, exposure, confounding, follow-up, outcome measurement and analysis.": "I segnali del full text sono organizzati attorno a selezione, esposizione, confondimento, follow-up, misurazione dell'outcome e analisi.", "The engine focuses on case definition, control selection, exposure ascertainment, confounding and analysis.": "Il motore si concentra su definizione dei casi, selezione dei controlli, accertamento dell'esposizione, confondimento e analisi.", "The engine separates sampling, exposure/outcome measurement, confounding and analysis rather than generating a checklist score.": "Il motore separa campionamento, misurazione di esposizione/outcome, confondimento e analisi invece di generare un punteggio da checklist.", "The engine focuses on representativeness, sampling, condition measurement, response and precision.": "Il motore si concentra su rappresentatività, campionamento, misurazione della condizione, risposta e precisione.", "Interpretive research requires human methodological judgement; EvidenceOS highlights auditable signals rather than generating a quality score.": "La ricerca interpretativa richiede giudizio metodologico umano; EvidenceOS evidenzia segnali verificabili invece di generare un punteggio di qualità.", "The engine assesses clarity and completeness of case definition, inclusion, measurement and reporting.": "Il motore valuta chiarezza e completezza di definizione dei casi, inclusione, misurazione e reporting.", "Case reports are appraised for diagnostic/clinical clarity and completeness rather than comparative causal inference.": "I case report vengono valutati per chiarezza e completezza diagnostica/clinica, non per inferenza causale comparativa.", "The engine structures signals around participants, predictors, outcome and analysis.": "Il motore struttura i segnali attorno a partecipanti, predittori, outcome e analisi.", "The engine examines perspective, comparators, costs/outcomes, time horizon, discounting and uncertainty.": "Il motore esamina prospettiva, comparatori, costi/outcome, orizzonte temporale, attualizzazione e incertezza.", "Guidelines require appraisal of scope, stakeholders, development rigour, clarity, applicability and editorial independence.": "Le linee guida richiedono appraisal di ambito, stakeholder, rigore dello sviluppo, chiarezza, applicabilità e indipendenza editoriale."};
const EOS_TEXT_ORIGINAL=new WeakMap();
const EOS_ATTR_ORIGINAL=new WeakMap();

function eosPatternTranslate(s){
 if(EOS_LANG!=='it')return s;
 let m;
 if((m=s.match(/^Updated (.+)$/)))return `Aggiornato ${m[1]}`;
 if((m=s.match(/^Project (PROJ-.+)$/)))return `Progetto ${m[1]}`;
 if((m=s.match(/^Approx\. ([\d.]+) MB stored locally · (\d+)% of a conservative 5 MB browser-storage estimate$/)))return `Circa ${m[1]} MB archiviati localmente · ${m[2]}% di una stima conservativa di 5 MB per lo storage del browser`;
 if((m=s.match(/^(\d+) study\/studies · (\d+) extracted result\(s\)$/)))return `${m[1]} studio/i · ${m[2]} risultato/i estratto/i`;
 if((m=s.match(/^(\d+) analysed studies\/results show a broadly consistent direction\.$/)))return `${m[1]} studi/risultati analizzati mostrano una direzione ampiamente coerente.`;
 if((m=s.match(/^(\d+) analysed full-text study\/studies are currently stored\.$/)))return `Sono attualmente salvati ${m[1]} studio/i full text analizzato/i.`;
 if((m=s.match(/^Body-level consistency: (.+)\.$/)))return `Coerenza a livello di body of evidence: ${eosTranslate(m[1])}.`;
 if((m=s.match(/^Methodological appraisal information: (.+)\.$/)))return `Informazioni sull'appraisal metodologico: ${eosTranslate(m[1])}.`;
 if((m=s.match(/^Precision information: (.+)\.$/)))return `Informazioni sulla precisione: ${eosTranslate(m[1])}.`;
 if((m=s.match(/^Only (\d+) analysed study\/studies contribute to this outcome\.$/)))return `Solo ${m[1]} studio/i analizzato/i contribuisce/contribuiscono a questo outcome.`;
 if((m=s.match(/^(\d+) analysed studies contribute to this outcome\.$/)))return `${m[1]} studi analizzati contribuiscono a questo outcome.`;
 if((m=s.match(/^Evidence addressing (.+) may be sparse\.$/)))return `Le evidenze relative a ${m[1]} potrebbero essere scarse.`;
 if((m=s.match(/^Evidence for (.+) may be insufficiently precise\.$/)))return `Le evidenze per ${m[1]} potrebbero essere insufficientemente precise.`;
 if((m=s.match(/^Inconsistency in evidence for (.+) may require explanation\.$/)))return `L'incoerenza delle evidenze per ${m[1]} potrebbe richiedere una spiegazione.`;
 if((m=s.match(/^Only one analysed study currently contributes to this outcome\.$/)))return `Attualmente un solo studio analizzato contribuisce a questo outcome.`;
 if((m=s.match(/^Confidence-interval information is incomplete in the currently analysed evidence\.$/)))return `Le informazioni sugli intervalli di confidenza sono incomplete nelle evidenze attualmente analizzate.`;
 if((m=s.match(/^The analysed results do not all point in the same direction\.$/)))return `I risultati analizzati non indicano tutti la stessa direzione.`;
 if((m=s.match(/^Several outcomes are currently represented by only one analysed study: (.+)$/)))return `Diversi outcome sono attualmente rappresentati da un solo studio analizzato: ${m[1]}`;
 if((m=s.match(/^(.+): results include effects in opposite directions\.$/)))return `${m[1]}: i risultati includono effetti in direzioni opposte.`;
 if((m=s.match(/^(.+): positive\/negative directional findings coexist with no-clear-difference results\.$/)))return `${m[1]}: risultati con direzione positiva/negativa coesistono con risultati senza una differenza chiara.`;
 if((m=s.match(/^The proposed (.+) gap is not supported by this anti-gap search: (\d+) direct counterexample\(s\) were identified\.$/)))return `Il gap di tipo ${eosTranslate(m[1])} proposto non è supportato da questa ricerca anti-gap: sono stati identificati ${m[2]} controesempi diretti.`;
 if((m=s.match(/^(\d+) direct counterexample\(s\) were found\. The original gap is too broad and should be narrowed rather than presented as an absence of research\.$/)))return `Sono stati trovati ${m[1]} controesempi diretti. Il gap originale è troppo ampio e dovrebbe essere ristretto invece di essere presentato come assenza di ricerca.`;
 if((m=s.match(/^The literature is not absent for (.+); the remaining question is whether existing evidence adequately resolves the (.+) limitation\.$/)))return `La letteratura su ${m[1]} non è assente; resta da stabilire se le evidenze esistenti risolvano adeguatamente la limitazione di ${eosTranslate(m[2])}.`;
 if((m=s.match(/^(\d+) directly relevant PubMed record\(s\) contain abstract-level language potentially inconsistent with the current conclusion\.$/)))return `${m[1]} record PubMed direttamente rilevanti contengono formulazioni a livello di abstract potenzialmente incoerenti con la conclusione corrente.`;
 if((m=s.match(/^(\d+) directly relevant systematic review\/meta-analysis record\(s\) may challenge the current conclusion\.$/)))return `${m[1]} record di revisione sistematica/meta-analisi direttamente rilevanti potrebbero mettere in discussione la conclusione corrente.`;
 if((m=s.match(/^(\d+) relevant record\(s\) explicitly signal longer-term\/follow-up evidence that may alter durability claims\.$/)))return `${m[1]} record rilevanti segnalano esplicitamente evidenze a più lungo termine/follow-up che potrebbero modificare le conclusioni sulla durata.`;
 if((m=s.match(/^Study saved: (.+)$/)))return `Studio salvato: ${m[1]}`;
 if((m=s.match(/^Challenge candidate added: (.+)$/)))return `Candidato del challenge aggiunto: ${m[1]}`;
 if((m=s.match(/^Challenge candidate PDF added: (.+)$/)))return `PDF del candidato del challenge aggiunto: ${m[1]}`;
 if((m=s.match(/^Gap (.+): (.+)$/)))return `Gap ${m[1]}: ${eosTranslate(m[2])}`;
 if((m=s.match(/^(.+): (survived|survived_with_qualification|materially_weakened|unresolved)$/)))return `${m[1]}: ${eosTranslate(m[2])}`;
 if((m=s.match(/^Could not import EvidenceOS project: (.+)$/)))return `Impossibile importare il progetto EvidenceOS: ${m[1]}`;
 if((m=s.match(/^Project validation failed \(HTTP (\d+)\)$/)))return `Validazione del progetto non riuscita (HTTP ${m[1]})`;
 if((m=s.match(/^Search failed \(HTTP (\d+)\)$/)))return `Ricerca non riuscita (HTTP ${m[1]})`;
 if((m=s.match(/^Study workspace failed \(HTTP (\d+)\)$/)))return `Study Workspace non riuscito (HTTP ${m[1]})`;
 if((m=s.match(/^Synthesis failed \(HTTP (\d+)\)$/)))return `Sintesi non riuscita (HTTP ${m[1]})`;
 if((m=s.match(/^Gap falsification failed \(HTTP (\d+)\)$/)))return `Falsificazione del gap non riuscita (HTTP ${m[1]})`;
 if((m=s.match(/^Conclusion challenge failed \(HTTP (\d+)\)$/)))return `Challenge della conclusione non riuscito (HTTP ${m[1]})`;
 if((m=s.match(/^Candidate intake failed \(HTTP (\d+)\)$/)))return `Importazione del candidato non riuscita (HTTP ${m[1]})`;
 return s;
}
function eosTranslate(value){
 const s=String(value??'');
 if(EOS_LANG!=='it')return s;
 return EOS_IT[s]||eosPatternTranslate(s);
}
function eosTranslateTextNode(node){
 if(!EOS_TEXT_ORIGINAL.has(node))EOS_TEXT_ORIGINAL.set(node,node.data);
 const original=EOS_TEXT_ORIGINAL.get(node);
 const next=EOS_LANG==='it'?eosTranslate(original):original;
 // Critical guard: assigning node.data fires a characterData mutation.
 // Never write when the rendered text is already correct, otherwise the
 // MutationObserver can recursively trigger itself and freeze the page.
 if(node.data!==next) node.data=next;
}
function eosTranslateAttrs(el){
 if(!(el instanceof Element))return;
 const attrs=['placeholder','title','aria-label'];
 let bag=EOS_ATTR_ORIGINAL.get(el);
 if(!bag){bag={};EOS_ATTR_ORIGINAL.set(el,bag)}
 attrs.forEach(a=>{
   if(el.hasAttribute(a)){
     if(!(a in bag))bag[a]=el.getAttribute(a);
     el.setAttribute(a,EOS_LANG==='it'?eosTranslate(bag[a]):bag[a]);
   }
 });
}
function eosWalk(root=document.body){
 if(!root)return;
 if(root.nodeType===Node.TEXT_NODE){eosTranslateTextNode(root);return}
 if(root.nodeType===Node.ELEMENT_NODE)eosTranslateAttrs(root);
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT|NodeFilter.SHOW_ELEMENT);
 let n;
 while((n=walker.nextNode())){
   if(n.nodeType===Node.TEXT_NODE)eosTranslateTextNode(n);
   else eosTranslateAttrs(n);
 }
}
function eosDate(value){
 try{return new Date(value).toLocaleString(EOS_LANG==='it'?'it-IT':'en-GB')}catch(_){return value}
}
function updateLanguageButtons(){
 document.querySelectorAll('[data-lang-choice]').forEach(b=>b.classList.toggle('active',b.dataset.langChoice===EOS_LANG));
 document.documentElement.lang=EOS_LANG;
}
function setLanguage(lang){
 EOS_LANG=lang==='it'?'it':'en';
 localStorage.setItem(LANG_KEY,EOS_LANG);
 updateLanguageButtons();
 eosWalk(document.body);
 // Re-render data-rich views so locale-sensitive dates are updated.
 try{renderProjectShell()}catch(_){}
 try{renderProjectHistory()}catch(_){}
 try{renderCorpus()}catch(_){}
 try{renderEvidenceGraph()}catch(_){}
}
const _nativeAlert=window.alert.bind(window),_nativeConfirm=window.confirm.bind(window),_nativePrompt=window.prompt.bind(window);
window.alert=(msg)=>_nativeAlert(eosTranslate(msg));
window.confirm=(msg)=>_nativeConfirm(eosTranslate(msg));
window.prompt=(msg,def='')=>_nativePrompt(eosTranslate(msg),eosTranslate(def));
const EOS_I18N_OBSERVER=new MutationObserver(ms=>{
 for(const m of ms){
   if(m.type==='characterData')eosTranslateTextNode(m.target);
   for(const n of m.addedNodes||[])eosWalk(n);
 }
});

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


function collectQuestion(){
 return {
   question:document.getElementById('qtext')?.value||'',
   population:document.getElementById('qpop')?.value||'',
   intervention:document.getElementById('qint')?.value||'',
   comparator:document.getElementById('qcomp')?.value||'',
   outcomes:document.getElementById('qout')?.value||'',
   timepoint:document.getElementById('qtime')?.value||''
 };
}
function applyQuestion(q={}){
 const map={qtext:'question',qpop:'population',qint:'intervention',qcomp:'comparator',qout:'outcomes',qtime:'timepoint'};
 Object.entries(map).forEach(([id,key])=>{const el=document.getElementById(id);if(el)el.value=q[key]||''});
}
let questionSaveTimer=null;
function scheduleQuestionSave(){
 clearTimeout(questionSaveTimer);
 questionSaveTimer=setTimeout(()=>{
   const p=getActiveProject();p.question=collectQuestion();saveProject(p);
 },350);
}
function bindQuestionAutosave(){
 ['qtext','qpop','qint','qcomp','qout','qtime'].forEach(id=>{
   const el=document.getElementById(id);if(el)el.addEventListener('input',scheduleQuestionSave);
 });
}
function newProject(){
 const name=prompt(eosTranslate('Project name'),eosTranslate('New evidence project'));if(!name)return;
 const projects=readProjects(),p=emptyProject(name.trim()||'New evidence project');
 projects.push(p);persistProjects(projects);localStorage.setItem(ACTIVE_PROJECT_KEY,p.project_id);
 applyProjectToUI(p);renderProjectShell();renderCorpus();renderEvidenceGraph();
 document.getElementById('synthResults').innerHTML='<div class="empty" style="height:260px"><div><strong>New project ready.</strong><div class="muted">Define the question and add full-text studies.</div></div></div>';
}
function switchProject(id){
 const projects=readProjects(),p=projects.find(x=>x.project_id===id);if(!p)return;
 localStorage.setItem(ACTIVE_PROJECT_KEY,id);applyProjectToUI(p);renderProjectShell();renderCorpus();
 if(p.latest_synthesis)renderSynthesis(p.latest_synthesis);else document.getElementById('synthResults').innerHTML='<div class="empty" style="height:260px"><div><strong>No synthesis yet for this project.</strong></div></div>';
 renderEvidenceGraph();
}
function renameActiveProject(name){
 const p=getActiveProject();p.name=(name||'').trim()||p.name;saveProject(p);
}
function applyProjectToUI(p){
 applyQuestion(p.question||{});
 const name=document.getElementById('projectName');if(name)name.value=p.name||'';
}
function renderProjectShell(){
 const state=ensureProjectState(),p=state.projects.find(x=>x.project_id===state.active)||state.projects[0];
 const sel=document.getElementById('projectSelect');
 if(sel){sel.innerHTML=state.projects.map(x=>`<option value="${esc(x.project_id)}" ${x.project_id===p.project_id?'selected':''}>${esc(x.name)}</option>`).join('')}
 const name=document.getElementById('projectName');if(name)name.value=p.name||'';
 const pill=document.getElementById('projectIdPill');if(pill)pill.textContent=`Project ${p.project_id}`;
 const sc=document.getElementById('projectStudyCount');if(sc)sc.textContent=(p.corpus||[]).length;
 const rc=document.getElementById('projectRevisionCount');if(rc)rc.textContent=(p.events||[]).length;
 const up=document.getElementById('projectUpdated');if(up)up.textContent=`Updated ${eosDate(p.updated_at)}`;
 renderProjectHistory();updateStorageMeter();
}
function renderProjectHistory(){
 const p=getActiveProject(),root=document.getElementById('projectHistory');if(!root)return;
 const events=(p.events||[]).slice(0,30);
 root.innerHTML=events.length?events.map(e=>`<div class="history-event"><b>${esc(e.label)}</b><span>${esc(e.event_type)} · ${eosDate(e.timestamp)}</span></div>`).join(''):'<div class="muted">No revisions yet. Synthesis, challenge and gap-falsification events will appear here.</div>';
}
function updateStorageMeter(){
 const projects=readProjects(),bytes=new Blob([JSON.stringify(projects)]).size,approxLimit=5*1024*1024;
 const pct=Math.min(100,Math.round(bytes/approxLimit*100));
 const bar=document.getElementById('storageMeter');if(bar)bar.style.width=`${pct}%`;
 const label=document.getElementById('storageLabel');if(label)label.textContent=`Approx. ${(bytes/1024/1024).toFixed(2)} MB stored locally · ${pct}% of a conservative 5 MB browser-storage estimate`;
}
function exportProject(){
 const p=getActiveProject();
 const blob=new Blob([JSON.stringify(p,null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=`EvidenceOS_${(p.name||'project').replace(/[^a-z0-9_-]+/gi,'_')}_${p.project_id}.json`;
 document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
 recordProjectEvent('export','Project exported as JSON',{});
}
async function importProjectFile(input){
 const f=input.files?.[0];if(!f)return;
 try{
   const raw=await f.text(),candidate=JSON.parse(raw);
   const r=await fetch('/v1/project/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:candidate})});
   const txt=await r.text();let d=null;try{d=JSON.parse(txt)}catch(_){}
   if(!r.ok)throw new Error(d?.detail||`Project validation failed (HTTP ${r.status})`);
   const p=d.project,projects=readProjects();
   // Avoid silently overwriting a local project with the same ID.
   if(projects.some(x=>x.project_id===p.project_id))p.project_id=uid('PROJ');
   p.name=`${p.name} (imported)`;
   p.events=p.events||[];
   p.events.unshift({event_id:uid('EVT'),event_type:'import',timestamp:isoNow(),label:'Project imported and validated',payload:{warnings:d.warnings||[]}});
   projects.push(p);persistProjects(projects);localStorage.setItem(ACTIVE_PROJECT_KEY,p.project_id);
   applyProjectToUI(p);renderProjectShell();renderCorpus();
   if(p.latest_synthesis)renderSynthesis(p.latest_synthesis);
   renderEvidenceGraph();
   if((d.warnings||[]).length)alert(d.warnings.join('\n'));
 }catch(e){alert(`Could not import EvidenceOS project: ${e.message}`)}
 finally{input.value=''}
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


const PROJECTS_KEY='evidenceos_v11_projects';
const ACTIVE_PROJECT_KEY='evidenceos_v11_active_project';
const LEGACY_CORPUS_KEY='evidenceos_v7_corpus';
const PROJECT_SCHEMA='11.0-alpha';

function isoNow(){return new Date().toISOString()}
function uid(prefix='PROJ'){return `${prefix}-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2,7).toUpperCase()}`}
function emptyProject(name='Untitled evidence project'){
 const now=isoNow();
 return {schema_version:PROJECT_SCHEMA,project_id:uid(),name,created_at:now,updated_at:now,
   question:{question:'',population:'',intervention:'',comparator:'',outcomes:'',timepoint:''},
   corpus:[],latest_synthesis:null,synthesis_history:[],events:[]};
}
function readProjects(){
 try{
   const x=JSON.parse(localStorage.getItem(PROJECTS_KEY)||'[]');
   return Array.isArray(x)?x:[];
 }catch(_){return []}
}
function persistProjects(items){
 try{
   localStorage.setItem(PROJECTS_KEY,JSON.stringify(items));
   updateStorageMeter();
 }catch(e){
   alert('Browser storage is full. Export this project as JSON before adding more evidence.');
   throw e;
 }
}
function ensureProjectState(){
 let projects=readProjects();
 if(!projects.length){
   const p=emptyProject('Evidence project 1');
   try{
     const legacy=JSON.parse(localStorage.getItem(LEGACY_CORPUS_KEY)||'[]');
     if(Array.isArray(legacy)&&legacy.length){p.corpus=legacy;p.events.push({event_id:uid('EVT'),event_type:'migration',timestamp:isoNow(),label:`Migrated ${legacy.length} legacy study/studies into v11`,payload:{count:legacy.length}})}
   }catch(_){}
   projects=[p];persistProjects(projects);localStorage.setItem(ACTIVE_PROJECT_KEY,p.project_id);
 }
 let active=localStorage.getItem(ACTIVE_PROJECT_KEY);
 if(!active||!projects.some(p=>p.project_id===active)){active=projects[0].project_id;localStorage.setItem(ACTIVE_PROJECT_KEY,active)}
 return {projects,active};
}
function getActiveProject(){
 const {projects,active}=ensureProjectState();
 return projects.find(p=>p.project_id===active)||projects[0];
}
function saveProject(project){
 const state=ensureProjectState(),projects=state.projects;
 project.updated_at=isoNow();
 const idx=projects.findIndex(p=>p.project_id===project.project_id);
 if(idx>=0)projects[idx]=project;else projects.push(project);
 persistProjects(projects);
 renderProjectShell();
}
function recordProjectEvent(type,label,payload={}){
 const p=getActiveProject();
 p.events=p.events||[];
 p.events.unshift({event_id:uid('EVT'),event_type:type,timestamp:isoNow(),label,payload});
 p.events=p.events.slice(0,2000);
 saveProject(p);
}
function getCorpus(){return getActiveProject().corpus||[]}
function setCorpus(items){
 const p=getActiveProject();p.corpus=items;saveProject(p);renderCorpus();renderEvidenceGraph();
}
function saveCurrentStudy(){
 const s=window._lastAnalysedStudy;if(!s)return;
 const items=getCorpus();
 const idx=items.findIndex(x=>x.report_id===s.report_id);
 if(idx>=0)items[idx]=s;else items.push(s);
 setCorpus(items);
 recordProjectEvent('study_saved',`Study saved: ${s.title}`,{report_id:s.report_id,design:s.design});
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
   const p=getActiveProject();
   p.latest_synthesis=d;
   p.synthesis_history=p.synthesis_history||[];
   p.synthesis_history.unshift({timestamp:isoNow(),headline:d.headline,confidence:d.confidence||{},outcomes:d.outcomes||[],gap_hypotheses:d.gap_hypotheses||[],contradictions:d.contradictions||[]});
   p.synthesis_history=p.synthesis_history.slice(0,250);
   p.events=p.events||[];
   p.events.unshift({event_id:uid('EVT'),event_type:'synthesis',timestamp:isoNow(),label:d.headline||'Evidence synthesis updated',payload:{studies:d.studies||0,outcomes:(d.outcomes||[]).length,confidence:d.confidence?.overall_label||null}});
   saveProject(p);
   renderEvidenceGraph();
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
   recordProjectEvent('gap_falsification',`Gap ${g.gap_id}: ${d.verdict}`,{gap:g,result:d});
   renderEvidenceGraph();
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
     recordProjectEvent('candidate_import',`Challenge candidate added: ${s.title}`,{report_id:s.report_id,source:s.provenance?.source||null});
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
   recordProjectEvent('conclusion_challenge',`${o.outcome}: ${d.verdict}`,{outcome:o.outcome,result:d});
   renderEvidenceGraph();
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
window.addEventListener('DOMContentLoaded',()=>{
 updateLanguageButtons();
 EOS_I18N_OBSERVER.observe(document.body,{subtree:true,childList:true,characterData:true});
 eosWalk(document.body);
 ensureProjectState();
 const p=getActiveProject();
 applyProjectToUI(p);
 renderProjectShell();
 renderCorpus();
 if(p.latest_synthesis)renderSynthesis(p.latest_synthesis);
 renderEvidenceGraph();
 bindQuestionAutosave();
 eosWalk(document.body);
});


function wrapLabel(text,max=24){
 const words=String(text||'').split(/\s+/),lines=[],cur=[];
 for(const w of words){
   if((cur.join(' ')+' '+w).trim().length>max&&cur.length){lines.push(cur.join(' '));cur.length=0}
   cur.push(w);
 }
 if(cur.length)lines.push(cur.join(' '));
 return lines.slice(0,3);
}
function graphNode(cls,x,y,w,h,label,sub=''){
 const lines=wrapLabel(label,Math.max(16,Math.floor(w/7)));
 const t=lines.map((line,i)=>`<text x="${x+10}" y="${y+20+i*14}">${esc(line)}</text>`).join('');
 const s=sub?`<text x="${x+10}" y="${y+h-9}" style="font-size:9px;fill:#65766f">${esc(sub)}</text>`:'';
 return `<g class="graph-node ${cls}"><rect x="${x}" y="${y}" rx="10" ry="10" width="${w}" height="${h}"></rect>${t}${s}</g>`;
}
function renderEvidenceGraph(){
 const root=document.getElementById('graphRoot');if(!root)return;
 const p=getActiveProject(),studies=p.corpus||[],syn=p.latest_synthesis;
 if(!studies.length&&!syn){root.className='graph-empty';root.innerHTML='Add analysed studies to this project to build the graph.';return}
 root.className='';
 const outcomes=syn?.outcomes||[],gaps=syn?.gap_hypotheses||[];
 const challengeEvents=(p.events||[]).filter(e=>e.event_type==='conclusion_challenge').slice(0,12);
 const width=1180,rowH=88;
 const rows=Math.max(studies.length,outcomes.length,gaps.length,challengeEvents.length,1);
 const height=Math.max(420,120+rows*rowH);
 const q={x:20,y:height/2-35,w:200,h:70};
 const sx=270,ox=520,cx=760,gx=980,nodeW=180,nodeH=62;
 let svg=`<svg viewBox="0 0 ${width} ${height}" width="100%" style="min-width:950px;height:auto">`;
 const qlabel=p.question?.question||p.name||'Research question';
 svg+=graphNode('graph-question',q.x,q.y,q.w,q.h,qlabel,'research question');

 studies.forEach((s,i)=>{
   const y=40+i*rowH;
   svg+=`<line class="graph-edge" x1="${q.x+q.w}" y1="${q.y+q.h/2}" x2="${sx}" y2="${y+nodeH/2}"/>`;
   svg+=graphNode('graph-study',sx,y,nodeW,nodeH,s.title,s.design||'study');
 });

 outcomes.forEach((o,i)=>{
   const y=40+i*rowH;
   const contributors=new Set(o.contributing_reports||[]);
   studies.forEach((s,j)=>{
     if(contributors.has(s.report_id)){
       const sy=40+j*rowH;
       svg+=`<line class="graph-edge" x1="${sx+nodeW}" y1="${sy+nodeH/2}" x2="${ox}" y2="${y+nodeH/2}"/>`;
     }
   });
   svg+=graphNode('graph-outcome',ox,y,nodeW,nodeH,o.outcome,`${o.dominant_direction} · ${o.consistency}`);
 });

 challengeEvents.forEach((e,i)=>{
   const outcome=e.payload?.outcome||'Conclusion challenge';
   const target=Math.max(0,outcomes.findIndex(o=>o.outcome===outcome));
   const ty=40+target*rowH,y=40+i*rowH;
   if(outcomes.length)svg+=`<line class="graph-edge" x1="${ox+nodeW}" y1="${ty+nodeH/2}" x2="${cx}" y2="${y+nodeH/2}"/>`;
   svg+=graphNode('graph-challenge',cx,y,nodeW,nodeH,outcome,e.payload?.result?.verdict||'challenge');
 });

 gaps.forEach((g,i)=>{
   const target=Math.max(0,outcomes.findIndex(o=>o.outcome===g.topic));
   const ty=40+target*rowH,y=40+i*rowH;
   if(outcomes.length)svg+=`<line class="graph-edge" x1="${ox+nodeW}" y1="${ty+nodeH/2}" x2="${gx}" y2="${y+nodeH/2}"/>`;
   svg+=graphNode('graph-gap',gx,y,170,nodeH,g.statement,g.gap_type);
 });
 svg+='</svg>';
 root.innerHTML=svg;
}

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
     recordProjectEvent('candidate_pdf',`Challenge candidate PDF added: ${s.title}`,{report_id:s.report_id});
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
