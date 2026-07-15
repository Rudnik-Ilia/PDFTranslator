from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    input_pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_dir: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(default="created", nullable=False)
    current_stage: Mapped[str] = mapped_column(default="created", nullable=False)
    total_pages: Mapped[int] = mapped_column(default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)

    blocks: Mapped[list[Block]] = relationship(back_populates="job", cascade="all, delete-orphan")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(index=True, nullable=False)
    block_order: Mapped[int] = mapped_column(nullable=False)
    reading_order: Mapped[int | None] = mapped_column(nullable=True)
    bbox: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    font_size: Mapped[float | None] = mapped_column(nullable=True)
    block_type: Mapped[str] = mapped_column(default="unknown", nullable=False)
    is_header_footer: Mapped[bool] = mapped_column(default=False, nullable=False)
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False)

    job: Mapped[Job] = relationship(back_populates="blocks")


class PlaceholderMapping(Base):
    __tablename__ = "placeholder_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    block_id: Mapped[int | None] = mapped_column(ForeignKey("blocks.id"), nullable=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id"), nullable=True)
    placeholder: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    page_start: Mapped[int] = mapped_column(nullable=False)
    page_end: Mapped[int] = mapped_column(nullable=False)
    block_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    protected_text: Mapped[str] = mapped_column(Text, nullable=False)
    relevant_glossary_terms: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    raw_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    job: Mapped[Job] = relationship(back_populates="chunks")


class RetryHistory(Base):
    __tablename__ = "retry_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"), index=True, nullable=False)
    attempt: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)


class OutputFile(Base):
    __tablename__ = "output_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
