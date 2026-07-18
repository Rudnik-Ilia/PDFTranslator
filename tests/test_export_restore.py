from dataclasses import dataclass
from pathlib import Path

from app.output.pdf_builder import write_translated_text_from_chunks


@dataclass
class FakeChunk:
    chunk_index: int
    page_start: int
    page_end: int
    status: str
    raw_translation: str | None
    edited_translation: str | None
    source_text: str


def test_text_export_restores_placeholders(tmp_path: Path) -> None:
    chunks = [
        FakeChunk(
            chunk_index=1,
            page_start=1,
            page_end=1,
            status="validated",
            raw_translation="Текст (⟦NUMBER_001⟧).",
            edited_translation=None,
            source_text="Text (42).",
        )
    ]
    path = write_translated_text_from_chunks(tmp_path, chunks, placeholder_map={"⟦NUMBER_001⟧": "42"})
    assert "⟦NUMBER_001⟧" not in path.read_text(encoding="utf-8")
    assert "Текст (42)." in path.read_text(encoding="utf-8")


def test_text_export_marks_broken_placeholders(tmp_path: Path) -> None:
    chunks = [FakeChunk(chunk_index=1, page_start=1, page_end=1, status="needs_review", raw_translation="Текст ⟦NUMBER", edited_translation=None, source_text="Text 42")]
    path = write_translated_text_from_chunks(tmp_path, chunks, placeholder_map={})
    text = path.read_text(encoding="utf-8")
    assert "⟦NUMBER" not in text
    assert "[ПОВРЕЖДЕННЫЙ ПЛЕЙСХОЛДЕР]" in text
