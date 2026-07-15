import re
from collections import Counter

from app.db.models import Block

_PAGE_NUMBER_RE = re.compile(r"^\s*(?:-\s*)?\d{1,4}(?:\s*-)?\s*$")
_NON_WORD_RE = re.compile(r"[^a-zA-Zа-яА-Я0-9]+")


def normalize_repeated_line(text: str) -> str:
    text = text.strip().lower()
    text = _NON_WORD_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_header_footer_blocks(blocks: list[Block], total_pages: int) -> set[int]:
    candidates: list[tuple[int, str]] = []
    for block in blocks:
        y0, y1 = block.bbox[1], block.bbox[3]
        page_height_guess = max(block.bbox[3], 1.0)
        in_top = y0 <= page_height_guess * 0.10 or y0 <= 80
        in_bottom = y1 >= page_height_guess * 0.90 or y1 >= 700
        if not (in_top or in_bottom):
            continue
        normalized = normalize_repeated_line(block.normalized_text)
        if not normalized or _PAGE_NUMBER_RE.match(block.normalized_text):
            candidates.append((block.id, "__page_number__"))
        else:
            candidates.append((block.id, normalized))
    counts = Counter(text for _, text in candidates)
    threshold = max(2, int(total_pages * 0.30))
    repeated = {text for text, count in counts.items() if count >= threshold}
    return {block_id for block_id, text in candidates if text in repeated}
