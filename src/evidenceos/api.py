from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import settings
from .extraction_engine_v1 import ExtractionEngineV1
from .evidence_schema_v1 import UniversalEvidenceRecord

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
        return ExtractResponse(record=ExtractionEngineV1().extract(
            request.report_id, request.title, request.text
        ))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("""<!doctype html>
<html><head><meta charset="utf-8"><title>EvidenceOS alpha</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;max-width:980px;margin:40px auto;padding:0 18px}
textarea,input{width:100%;box-sizing:border-box;margin:.3rem 0 1rem;padding:.7rem}
textarea{min-height:300px}button{padding:.7rem 1rem}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}</style>
</head><body>
<h1>EvidenceOS <small>alpha</small></h1>
<p>Paste report text to create a provenance-aware Universal Evidence Record.</p>
<label>Report ID</label><input id="rid" value="DEMO-001">
<label>Title</label><input id="ttl" value="Demo randomized trial">
<label>Report text</label><textarea id="txt"></textarea>
<button onclick="run()">Extract</button><pre id="out">Result will appear here.</pre>
<script>
async function run(){
 const r=await fetch('/v1/extract',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({report_id:rid.value,title:ttl.value,text:txt.value})});
 out.textContent=JSON.stringify(await r.json(),null,2);
}
</script></body></html>""")
