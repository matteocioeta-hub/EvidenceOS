from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .evidence_schema_v1 import UniversalEvidenceRecord
from .extraction_engine_v1 import ExtractionEngineV1
from .universal_trust_engine import UniversalTrustAssessment, assess_full_text


IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
OAI_URL = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"


class CandidateIntakeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    pmid: str | None = None
    doi: str | None = None


class CandidateIntakeResponse(BaseModel):
    mode: Literal["auto_imported", "pdf_required"]
    report_id: str
    title: str
    pmid: str | None = None
    doi: str | None = None
    pmcid: str | None = None
    license: str | None = None
    message: str
    record: UniversalEvidenceRecord | None = None
    trust_assessment: UniversalTrustAssessment | None = None
    extracted_characters: int | None = None


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _clean_text(parts) -> str:
    text = " ".join(x.strip() for x in parts if x and x.strip())
    return re.sub(r"\s+", " ", text).strip()


class PMCCandidateIntake:
    """
    Conservative commercial-safe intake.

    Auto-import is attempted only for PMC records whose OA API license is
    clearly CC0 or CC BY. Other cases fall back to user-provided PDF.
    """

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            headers={
                "User-Agent": "EvidenceOS/0.1",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        self.tool = os.environ.get("NCBI_TOOL", "EvidenceOS")
        self.email = os.environ.get("NCBI_EMAIL")

    def _idconv_params(self, identifier: str) -> dict:
        params = {
            "ids": identifier,
            "format": "json",
            "tool": self.tool,
        }
        if self.email:
            params["email"] = self.email
        return params

    def lookup_pmcid(self, pmid: str | None, doi: str | None) -> str | None:
        identifier = (pmid or doi or "").strip()
        if not identifier:
            return None
        response = self.client.get(IDCONV_URL, params=self._idconv_params(identifier))
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records") or []
        if not records:
            return None
        rec = records[0]
        pmcid = rec.get("pmcid")
        if not pmcid:
            return None
        # Embargoed/non-live records are not auto-imported.
        if rec.get("live") is False:
            return None
        return str(pmcid)

    @staticmethod
    def _commercial_license_ok(license_name: str | None) -> bool:
        if not license_name:
            return False
        norm = re.sub(r"\s+", " ", license_name.strip().upper())
        # Intentionally narrow for a commercial alpha.
        if norm.startswith("CC0"):
            return True
        return bool(re.fullmatch(r"CC BY(?: [1-9](?:\.\d)?)?", norm))

    def oa_license(self, pmcid: str) -> str | None:
        response = self.client.get(OA_URL, params={"id": pmcid})
        response.raise_for_status()
        root = ET.fromstring(response.text)
        record = next((x for x in root.iter() if _local(x.tag) == "record"), None)
        if record is None:
            return None
        return record.attrib.get("license")

    def fetch_reusable_full_text(self, pmcid: str) -> str:
        numeric = re.sub(r"^PMC", "", pmcid, flags=re.I)
        params = {
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{numeric}",
            "metadataPrefix": "pmc",
        }
        response = self.client.get(OAI_URL, params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)

        error = next((x for x in root.iter() if _local(x.tag) == "error"), None)
        if error is not None:
            raise RuntimeError(_clean_text(error.itertext()) or "PMC OAI full text unavailable.")

        article = next((x for x in root.iter() if _local(x.tag) == "article"), None)
        if article is None:
            raise RuntimeError("PMC OAI response did not contain reusable article full text.")

        title_node = next((x for x in article.iter() if _local(x.tag) == "article-title"), None)
        abstract_node = next((x for x in article.iter() if _local(x.tag) == "abstract"), None)
        body_node = next((x for x in article.iter() if _local(x.tag) == "body"), None)

        chunks = []
        if title_node is not None:
            chunks.append("TITLE\n" + _clean_text(title_node.itertext()))
        if abstract_node is not None:
            chunks.append("ABSTRACT\n" + _clean_text(abstract_node.itertext()))
        if body_node is not None:
            # JATS includes tables/captions inside the body tree. Keep them in the
            # text stream because they may contain outcome data.
            chunks.append("FULL TEXT\n" + _clean_text(body_node.itertext()))

        text = "\n\n".join(x for x in chunks if x.strip())
        if len(text) < 500:
            raise RuntimeError("Reusable PMC full text was retrieved but contained too little analysable text.")
        return text


def intake_candidate(req: CandidateIntakeRequest) -> CandidateIntakeResponse:
    report_id = f"PMID:{req.pmid}" if req.pmid else (f"DOI:{req.doi}" if req.doi else "CANDIDATE")
    client = PMCCandidateIntake()

    try:
        pmcid = client.lookup_pmcid(req.pmid, req.doi)
    except Exception:
        pmcid = None

    if not pmcid:
        return CandidateIntakeResponse(
            mode="pdf_required",
            report_id=report_id,
            title=req.title,
            pmid=req.pmid,
            doi=req.doi,
            message="No reusable PMC full text was identified automatically. Upload the full-text PDF to continue.",
        )

    try:
        license_name = client.oa_license(pmcid)
    except Exception:
        license_name = None

    if not client._commercial_license_ok(license_name):
        return CandidateIntakeResponse(
            mode="pdf_required",
            report_id=report_id,
            title=req.title,
            pmid=req.pmid,
            doi=req.doi,
            pmcid=pmcid,
            license=license_name,
            message=(
                "The article is in PMC, but EvidenceOS did not verify a sufficiently permissive "
                "commercial-use license for automatic ingestion. Upload your full-text PDF instead."
            ),
        )

    try:
        text = client.fetch_reusable_full_text(pmcid)
        record = ExtractionEngineV1().extract(report_id, req.title, text)
        trust = assess_full_text(report_id, req.title, text)
    except Exception as exc:
        return CandidateIntakeResponse(
            mode="pdf_required",
            report_id=report_id,
            title=req.title,
            pmid=req.pmid,
            doi=req.doi,
            pmcid=pmcid,
            license=license_name,
            message=(
                "PMC metadata permits automatic reuse, but full-text ingestion was not completed. "
                f"Upload the PDF instead. ({str(exc)[:180]})"
            ),
        )

    return CandidateIntakeResponse(
        mode="auto_imported",
        report_id=report_id,
        title=req.title,
        pmid=req.pmid,
        doi=req.doi,
        pmcid=pmcid,
        license=license_name,
        message=(
            "Reusable PMC full text was imported automatically, appraised, and is ready to enter the evidence corpus."
        ),
        record=record,
        trust_assessment=trust,
        extracted_characters=len(text),
    )
