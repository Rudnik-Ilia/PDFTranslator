from app.db.models import Block


def extract_term_candidates(blocks: list[Block]) -> list[str]:
    # Placeholder deterministic MVP hook. Full frequency/pattern extraction comes next.
    terms: set[str] = set()
    for block in blocks:
        if block.block_type in {"title", "heading"}:
            text = block.normalized_text.strip()
            if 3 <= len(text) <= 120:
                terms.add(text)
    return sorted(terms)
