from app.db.models import Block
from app.pdf.placeholders import protect_text

TRANSLATABLE_TYPES = {
    "title",
    "heading",
    "paragraph",
    "list_item",
    "table",
    "table_caption",
    "figure_caption",
    "footnote",
    "bibliography",
    "unknown",
}


def build_chunks(blocks: list[Block], max_chars: int = 4500) -> tuple[list[dict], list[tuple[int | None, str, str, str]]]:
    chunks: list[dict] = []
    placeholder_records: list[tuple[int | None, str, str, str]] = []
    current_blocks: list[Block] = []
    current_source: list[str] = []
    current_protected: list[str] = []
    placeholder_index = 1

    def flush() -> None:
        nonlocal current_blocks, current_source, current_protected
        if not current_blocks:
            return
        chunks.append(
            {
                "chunk_index": len(chunks) + 1,
                "page_start": min(b.page_number for b in current_blocks),
                "page_end": max(b.page_number for b in current_blocks),
                "block_ids": [b.id for b in current_blocks],
                "source_text": "\n\n".join(current_source),
                "protected_text": "\n\n".join(current_protected),
                "relevant_glossary_terms": [],
            }
        )
        current_blocks = []
        current_source = []
        current_protected = []

    for block in blocks:
        if block.is_header_footer or block.block_type not in TRANSLATABLE_TYPES:
            continue
        text = block.normalized_text
        protected, mappings, placeholder_index = protect_text(text, placeholder_index)
        for mapping in mappings:
            placeholder_records.append((block.id, mapping.placeholder, mapping.original, mapping.kind))
        projected_len = len("\n\n".join([*current_protected, protected]))
        starts_new_section = block.block_type in {"heading", "title"}
        if current_blocks and projected_len > max_chars and not starts_new_section:
            flush()
        current_blocks.append(block)
        current_source.append(text)
        current_protected.append(protected)
    flush()
    return chunks, placeholder_records
