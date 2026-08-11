from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


MAX_PDF_BYTES = 20 * 1024 * 1024
MIN_EXTRACTED_CHARS = 300


class PdfIngestError(ValueError):
    pass


def extract_pdf_text(data: bytes) -> tuple[str, int]:
    if not data:
        raise PdfIngestError("The uploaded PDF is empty.")

    if len(data) > MAX_PDF_BYTES:
        raise PdfIngestError("PDF exceeds the 20 MB upload limit.")

    if not data.startswith(b"%PDF"):
        raise PdfIngestError("The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise PdfIngestError("EvidenceOS could not open this PDF.") from exc

    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = 0
        if not unlocked:
            raise PdfIngestError("Password-protected PDFs are not supported.")

    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append(f"\n--- PAGE {index} ---\n{text}")

    extracted = "\n".join(pages).strip()

    if len(extracted) < MIN_EXTRACTED_CHARS:
        raise PdfIngestError(
            "Very little machine-readable text was found. "
            "This PDF may be scanned or image-only. OCR is not enabled in the public alpha."
        )

    return extracted, len(reader.pages)
