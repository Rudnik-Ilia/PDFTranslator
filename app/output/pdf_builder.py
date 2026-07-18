from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Protocol

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.db.models import Chunk

_BROKEN_PLACEHOLDER_RE = re.compile(r"⟦[A-Z_]+(?:_\d*)?(?=\s|<|$)")


class TranslationChunkLike(Protocol):
    chunk_index: int
    page_start: int
    page_end: int
    status: str
    raw_translation: str | None
    edited_translation: str | None
    source_text: str


def _restore_placeholders(text: str, placeholder_map: dict[str, str] | None) -> str:
    restored = text
    if placeholder_map:
        for placeholder, original in placeholder_map.items():
            restored = restored.replace(placeholder, original)
    return _BROKEN_PLACEHOLDER_RE.sub("[ПОВРЕЖДЕННЫЙ ПЛЕЙСХОЛДЕР]", restored)


def _chunk_translation(chunk: TranslationChunkLike | Chunk, placeholder_map: dict[str, str] | None = None) -> str:
    translation = (chunk.edited_translation or chunk.raw_translation or "").strip()
    return _restore_placeholders(translation, placeholder_map)


def _chunk_text(chunk: TranslationChunkLike | Chunk, *, include_missing_markers: bool, placeholder_map: dict[str, str] | None = None) -> str:
    translation = _chunk_translation(chunk, placeholder_map)
    if translation:
        return translation
    if not include_missing_markers:
        return ""
    return (
        f"[ФРАГМЕНТ НЕ ПЕРЕВЕДЕН: chunk {chunk.chunk_index}, "
        f"pages {chunk.page_start}-{chunk.page_end}, status={chunk.status}]"
    )


def write_translated_text(output_dir: Path, translations: list[str]) -> Path:
    path = output_dir / "translated_ru.txt"
    path.write_text("\n\n".join(t for t in translations if t.strip()), encoding="utf-8")
    return path


def write_translated_text_from_chunks(
    output_dir: Path,
    chunks: list[Chunk] | list[TranslationChunkLike],
    *,
    include_missing_markers: bool = True,
    placeholder_map: dict[str, str] | None = None,
) -> Path:
    path = output_dir / "translated_ru.txt"
    parts: list[str] = []
    for chunk in chunks:
        text = _chunk_text(chunk, include_missing_markers=include_missing_markers, placeholder_map=placeholder_map)
        if not text:
            continue
        parts.append(f"<!-- chunk {chunk.chunk_index}, pages {chunk.page_start}-{chunk.page_end}, status={chunk.status} -->\n{text}")
    path.write_text("\n\n".join(parts), encoding="utf-8")
    return path


def _register_cyrillic_font() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            font_name = candidate.stem.replace("-", "_")
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
            return font_name
    return "Helvetica"


def write_translated_pdf_from_chunks(output_dir: Path, chunks: list[TranslationChunkLike] | list[Chunk], *, include_missing_markers: bool = True, placeholder_map: dict[str, str] | None = None, title: str = "Russian Translation Draft") -> Path:
    path = output_dir / "translated_ru.pdf"
    font_name = _register_cyrillic_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RussianTitle", parent=styles["Title"], fontName=font_name, fontSize=18, leading=24, spaceAfter=18)
    meta_style = ParagraphStyle("ChunkMeta", parent=styles["Normal"], fontName=font_name, fontSize=8, leading=10, textColor=HexColor("#666666"), spaceBefore=8, spaceAfter=4,)
    body_style = ParagraphStyle("RussianBody", parent=styles["BodyText"], fontName=font_name, fontSize=10.5, leading=15, firstLineIndent=0.5 * cm, spaceAfter=8)
    missing_style = ParagraphStyle("MissingChunk", parent=body_style, textColor=HexColor("#990000"), firstLineIndent=0)

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=1.8 * cm, leftMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm, title=title)
    story = [Paragraph(escape(title), title_style), Spacer(1, 0.3 * cm)]
    translated_count: int = 0
    missing_count: int = 0
    for chunk in chunks:
        translation = _chunk_translation(chunk, placeholder_map)
        if translation:
            translated_count += 1
        else:
            missing_count += 1
        text = _chunk_text(chunk, include_missing_markers=include_missing_markers, placeholder_map=placeholder_map)
        if not text:
            continue
        story.append(Paragraph(escape(f"chunk {chunk.chunk_index} · pages {chunk.page_start}-{chunk.page_end} · status={chunk.status}"), meta_style))
        style = body_style if translation else missing_style
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        for paragraph in paragraphs:
            story.append(Paragraph(escape(paragraph).replace("\n", "<br/>") or " ", style))
    story.insert(2, Paragraph(escape(f"Draft export: translated chunks={translated_count}, missing chunks={missing_count}"), meta_style))
    story.insert(3, PageBreak())
    doc.build(story)
    return path


def rebuild_pdf_placeholder(output_dir: Path) -> Path | None:
    # Kept for backward compatibility with earlier pipeline code paths.
    return None
