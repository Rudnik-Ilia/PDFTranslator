import re
from pathlib import Path

import fitz

_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"^[\w'-]+$", re.UNICODE)


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def collapse_adjacent_duplicate_words(text: str) -> str:
    """Collapse PDF-rendering duplicate words in short display/title blocks.

    Some PDFs draw large title text twice, for shadow/bold effects. PyMuPDF can expose
    that as adjacent repeated words: "Science Science". Restrict this to short blocks
    so normal prose is not aggressively rewritten.
    """
    if len(text) > 160:
        return text
    tokens = text.split()
    if len(tokens) < 2:
        return text
    collapsed: list[str] = []
    duplicate_pairs = 0
    for token in tokens:
        comparable = token.strip(".,;:!?()[]{}\"'").casefold()
        previous = collapsed[-1].strip(".,;:!?()[]{}\"'").casefold() if collapsed else None
        if previous == comparable and _WORD_RE.match(token.strip(".,;:!?()[]{}\"'")):
            duplicate_pairs += 1
            continue
        collapsed.append(token)
    if duplicate_pairs == 0:
        return text
    return " ".join(collapsed)


def extract_blocks(path: Path) -> list[dict]:
    extracted: list[dict] = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            data = page.get_text("dict")
            blocks = data.get("blocks", [])
            order = 0
            for block in blocks:
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                line_texts: list[str] = []
                font_sizes: list[float] = []
                for line in lines:
                    span_texts: list[str] = []
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        if span_text:
                            span_texts.append(span_text)
                        size = span.get("size")
                        if isinstance(size, int | float):
                            font_sizes.append(float(size))
                    if span_texts:
                        line_texts.append("".join(span_texts))
                raw = "\n".join(line_texts)
                normalized = collapse_adjacent_duplicate_words(normalize_whitespace(raw))
                if not normalized:
                    continue
                order += 1
                bbox = [float(v) for v in block.get("bbox", [0, 0, 0, 0])]
                font_size = sum(font_sizes) / len(font_sizes) if font_sizes else None
                extracted.append(
                    {
                        "page_number": page_index,
                        "block_order": order,
                        "bbox": bbox,
                        "raw_text": raw,
                        "normalized_text": normalized,
                        "font_size": font_size,
                    }
                )
    return extracted
