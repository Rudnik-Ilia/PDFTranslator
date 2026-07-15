from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.db.models import Block, Chunk, Job, OutputFile, PlaceholderMapping, RetryHistory


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(self, input_pdf_path: Path, output_dir: Path) -> Job:
        existing = self.session.scalar(
            select(Job).where(
                Job.input_pdf_path == str(input_pdf_path),
                Job.output_dir == str(output_dir),
                Job.status != "finished",
            )
        )
        if existing:
            return existing
        job = Job(input_pdf_path=str(input_pdf_path), output_dir=str(output_dir))
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, job_id: int) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job

    def latest_job(self) -> Job:
        job = self.session.scalar(select(Job).order_by(Job.id.desc()).limit(1))
        if job is None:
            raise ValueError("No jobs found in project_state.sqlite")
        return job

    def update_job(self, job_id: int, *, stage: str | None = None, status: str | None = None, total_pages: int | None = None, metadata: dict | None = None) -> None:
        job = self.get_job(job_id)
        if stage is not None:
            job.current_stage = stage
        if status is not None:
            job.status = status
        if total_pages is not None:
            job.total_pages = total_pages
        if metadata is not None:
            job.metadata_json = {**job.metadata_json, **metadata}
        job.updated_at = datetime.now(UTC)
        self.session.flush()

    def add_blocks(self, job_id: int, blocks: list[dict]) -> None:
        if self.session.scalar(select(Block.id).where(Block.job_id == job_id).limit(1)):
            return
        self.session.add_all(Block(job_id=job_id, **block) for block in blocks)
        self.session.flush()

    def blocks(self, job_id: int, include_headers: bool = True) -> list[Block]:
        stmt: Select[tuple[Block]] = select(Block).where(Block.job_id == job_id)
        if not include_headers:
            stmt = stmt.where(Block.is_header_footer.is_(False))
        stmt = stmt.order_by(Block.page_number, Block.reading_order.nulls_last(), Block.block_order)
        return list(self.session.scalars(stmt))

    def update_block_reading_order(self, block_id: int, reading_order: int, needs_review: bool = False) -> None:
        block = self.session.get(Block, block_id)
        if block:
            block.reading_order = reading_order
            block.needs_review = needs_review

    def mark_blocks_header_footer(self, block_ids: set[int]) -> None:
        if not block_ids:
            return
        for block in self.session.scalars(select(Block).where(Block.id.in_(block_ids))):
            block.is_header_footer = True
            if block.block_type == "unknown":
                block.block_type = "header" if block.bbox[1] < 200 else "footer"

    def update_block_type(self, block_id: int, block_type: str) -> None:
        block = self.session.get(Block, block_id)
        if block:
            block.block_type = block_type

    def add_placeholder(self, job_id: int, block_id: int | None, chunk_id: int | None, placeholder: str, original_text: str, kind: str) -> None:
        self.session.add(
            PlaceholderMapping(
                job_id=job_id,
                block_id=block_id,
                chunk_id=chunk_id,
                placeholder=placeholder,
                original_text=original_text,
                kind=kind,
            )
        )

    def placeholders_for_job(self, job_id: int) -> list[PlaceholderMapping]:
        return list(self.session.scalars(select(PlaceholderMapping).where(PlaceholderMapping.job_id == job_id)))

    def delete_chunks_and_placeholders(self, job_id: int) -> None:
        self.session.execute(delete(RetryHistory).where(RetryHistory.job_id == job_id))
        self.session.execute(delete(PlaceholderMapping).where(PlaceholderMapping.job_id == job_id))
        self.session.execute(delete(Chunk).where(Chunk.job_id == job_id))
        self.session.flush()

    def add_chunks(self, job_id: int, chunks: list[dict]) -> None:
        if self.session.scalar(select(Chunk.id).where(Chunk.job_id == job_id).limit(1)):
            return
        self.session.add_all(Chunk(job_id=job_id, **chunk) for chunk in chunks)
        self.session.flush()

    def chunks(self, job_id: int) -> list[Chunk]:
        return list(self.session.scalars(select(Chunk).where(Chunk.job_id == job_id).order_by(Chunk.chunk_index)))

    def next_pending_chunk(self, job_id: int) -> Chunk | None:
        return self.session.scalar(
            select(Chunk)
            .where(Chunk.job_id == job_id, Chunk.status.in_(["pending", "needs_retry"]))
            .order_by(Chunk.chunk_index)
            .limit(1)
        )

    def update_chunk_translation(self, chunk_id: int, translation: str, status: str = "translated") -> None:
        chunk = self.session.get(Chunk, chunk_id)
        if chunk is None:
            return
        chunk.raw_translation = translation
        chunk.status = status

    def update_chunk_validation(self, chunk_id: int, status: str, errors: list[str]) -> None:
        chunk = self.session.get(Chunk, chunk_id)
        if chunk is None:
            return
        chunk.status = status
        chunk.validation_errors = errors

    def increment_retry(self, job_id: int, chunk_id: int, reason: str) -> int:
        chunk = self.session.get(Chunk, chunk_id)
        if chunk is None:
            raise ValueError(f"Chunk {chunk_id} not found")
        chunk.retry_count += 1
        chunk.status = "needs_retry"
        self.session.add(RetryHistory(job_id=job_id, chunk_id=chunk_id, attempt=chunk.retry_count, reason=reason))
        return chunk.retry_count

    def add_output(self, job_id: int, kind: str, path: Path) -> None:
        self.session.add(OutputFile(job_id=job_id, kind=kind, path=str(path)))
