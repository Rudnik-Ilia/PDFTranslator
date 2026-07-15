from pathlib import Path

import fitz
from pydantic import BaseModel

SCANNED_PDF_MESSAGE = (
    "This PDF appears to be scanned or has insufficient selectable text. OCR is not supported in MVP."
)


class PDFAnalysis(BaseModel):
    page_count: int
    sampled_text_chars: int
    is_text_based: bool


def analyze_pdf(path: Path, min_text_chars: int = 200, sample_pages: int = 5) -> PDFAnalysis:
    if not path.exists():
        raise FileNotFoundError(path)
    with fitz.open(path) as doc:
        page_count = doc.page_count
        text_parts: list[str] = []
        for page in doc[: min(sample_pages, page_count)]:
            text_parts.append(page.get_text("text"))
    sampled_chars = len("\n".join(text_parts).strip())
    return PDFAnalysis(
        page_count=page_count,
        sampled_text_chars=sampled_chars,
        is_text_based=sampled_chars >= min_text_chars,
    )
