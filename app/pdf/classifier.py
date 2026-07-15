import re

from app.db.models import Block

_FORMULA_RE = re.compile(r"[=∑∫√≈≤≥±]|\b(?:equation|where)\b", re.IGNORECASE)
_CITATION_LINE_RE = re.compile(r"^\s*\[\d+\]|^\s*references\s*$", re.IGNORECASE)
_CAPTION_RE = re.compile(r"^(fig\.|figure|table)\s+\d+", re.IGNORECASE)
_LIST_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+")


def classify_block(block: Block) -> str:
    text = block.normalized_text
    lower = text.lower()
    if block.is_header_footer:
        return block.block_type if block.block_type in {"header", "footer", "page_number"} else "header"
    if _CITATION_LINE_RE.match(text) or lower in {"references", "bibliography"}:
        return "bibliography"
    if _CAPTION_RE.match(text):
        return "figure_caption" if lower.startswith(("fig", "figure")) else "table_caption"
    if _FORMULA_RE.search(text) and len(text) < 240:
        return "formula"
    if _LIST_RE.match(text):
        return "list_item"
    if block.font_size and block.font_size >= 16 and len(text) < 180:
        return "title"
    if len(text) < 140 and (text.istitle() or text.isupper() or re.match(r"^\d+(?:\.\d+)*\s+", text)):
        return "heading"
    if len(text) > 20:
        return "paragraph"
    return "unknown"
