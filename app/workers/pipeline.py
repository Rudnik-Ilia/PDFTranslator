from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import sessionmaker

from app.core.config import PipelineConfig
from app.db.models import Chunk
from app.db.repository import Repository
from app.db.session import create_session_factory, session_scope
from app.glossary.builder import write_glossary_csv
from app.glossary.extractor import extract_term_candidates
from app.output.html_review import generate_bilingual_review_placeholder
from app.output.pdf_builder import (
    write_translated_pdf_from_chunks,
    write_translated_text_from_chunks,
)
from app.output.qa_report import generate_quality_report_placeholder
from app.pdf.analyzer import SCANNED_PDF_MESSAGE, analyze_pdf
from app.pdf.classifier import classify_block
from app.pdf.cleaner import detect_header_footer_blocks
from app.pdf.extractor import extract_blocks
from app.pdf.reading_order import resolve_page_orders
from app.translation.chunker import build_chunks
from app.translation.llm_client import LLMClientError
from app.translation.post_editor import post_edit_translation
from app.translation.translator import translate_chunk
from app.validation.deterministic import validate_translation
from app.validation.retry import retry_reason, should_retry
from app.workers.state import PipelineState

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


class PDFTranslationPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.session_factory = create_session_factory(config.output_dir)
        self.graph = self._build_graph()

    def run(self) -> PipelineState:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            job = repo.create_job(self.config.input_pdf_path, self.config.output_dir)
            state: PipelineState = {
                "job_id": job.id,
                "input_pdf_path": str(self.config.input_pdf_path),
                "output_dir": str(self.config.output_dir),
                "current_stage": job.current_stage,
                "total_pages": job.total_pages,
                "current_chunk_id": None,
                "chunks_total": 0,
                "chunks_done": 0,
                "retry_count": 0,
                "validation_errors": [],
                "consecutive_llm_errors": 0,
                "final_outputs": {},
            }
        return self.graph.invoke(state)

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("analyze_pdf", self._analyze_pdf)
        graph.add_node("extract_blocks", self._extract_blocks)
        graph.add_node("resolve_reading_order", self._resolve_reading_order)
        graph.add_node("remove_headers_footers", self._remove_headers_footers)
        graph.add_node("classify_blocks", self._classify_blocks)
        graph.add_node("protect_placeholders", self._protect_placeholders)
        graph.add_node("extract_glossary", self._extract_glossary)
        graph.add_node("build_chunks", self._build_chunks)
        graph.add_node("translate_chunk", self._translate_chunk)
        graph.add_node("validate_chunk", self._validate_chunk)
        graph.add_node("retry_or_split_chunk", self._retry_or_split_chunk)
        graph.add_node("meaning_check_chunk", self._meaning_check_chunk)
        graph.add_node("terminology_check_chunk", self._terminology_check_chunk)
        graph.add_node("russian_academic_post_edit", self._russian_academic_post_edit)
        graph.add_node("final_validate_chunk", self._final_validate_chunk)
        graph.add_node("rebuild_pdf", self._rebuild_pdf)
        graph.add_node("generate_bilingual_review", self._generate_bilingual_review)
        graph.add_node("generate_quality_report", self._generate_quality_report)
        graph.add_node("finish_job", self._finish_job)

        graph.set_entry_point("analyze_pdf")
        graph.add_edge("analyze_pdf", "extract_blocks")
        graph.add_edge("extract_blocks", "resolve_reading_order")
        graph.add_edge("resolve_reading_order", "remove_headers_footers")
        graph.add_edge("remove_headers_footers", "classify_blocks")
        graph.add_edge("classify_blocks", "protect_placeholders")
        graph.add_edge("protect_placeholders", "extract_glossary")
        graph.add_edge("extract_glossary", "build_chunks")
        graph.add_conditional_edges(
            "build_chunks",
            self._after_build_chunks,
            {"translate": "translate_chunk", "outputs": "rebuild_pdf"},
        )
        graph.add_conditional_edges(
            "translate_chunk",
            self._after_translation,
            {
                "validate": "validate_chunk",
                "retry": "retry_or_split_chunk",
                "next_chunk": "translate_chunk",
                "outputs": "rebuild_pdf",
            },
        )
        graph.add_conditional_edges(
            "validate_chunk",
            self._after_validation,
            {
                "retry": "retry_or_split_chunk",
                "meaning_check": "meaning_check_chunk",
                "post_edit": "russian_academic_post_edit",
                "next_chunk": "translate_chunk",
                "outputs": "rebuild_pdf",
            },
        )
        graph.add_edge("retry_or_split_chunk", "translate_chunk")
        graph.add_edge("meaning_check_chunk", "terminology_check_chunk")
        graph.add_conditional_edges(
            "terminology_check_chunk",
            self._after_optional_checks,
            {"post_edit": "russian_academic_post_edit", "next_chunk": "translate_chunk", "outputs": "rebuild_pdf"},
        )
        graph.add_edge("russian_academic_post_edit", "final_validate_chunk")
        graph.add_conditional_edges(
            "final_validate_chunk",
            self._after_final_validation,
            {"next_chunk": "translate_chunk", "outputs": "rebuild_pdf"},
        )
        graph.add_edge("rebuild_pdf", "generate_bilingual_review")
        graph.add_edge("generate_bilingual_review", "generate_quality_report")
        graph.add_edge("generate_quality_report", "finish_job")
        graph.add_edge("finish_job", END)
        return graph.compile()

    def _repo(self, factory: sessionmaker, state: PipelineState):
        return session_scope(factory)

    def _set_stage(self, repo: Repository, state: PipelineState, stage: str) -> None:
        repo.update_job(state["job_id"], stage=stage)
        state["current_stage"] = stage

    def _analyze_pdf(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "analyze_pdf")
            analysis = analyze_pdf(Path(state["input_pdf_path"]), self.config.min_text_chars_for_text_pdf)
            if not analysis.is_text_based:
                repo.update_job(state["job_id"], status="rejected", metadata=analysis.model_dump())
                raise PipelineError(SCANNED_PDF_MESSAGE)
            repo.update_job(state["job_id"], status="accepted", total_pages=analysis.page_count, metadata=analysis.model_dump())
            state["total_pages"] = analysis.page_count
        return state

    def _extract_blocks(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "extract_blocks")
            blocks = extract_blocks(Path(state["input_pdf_path"]))
            repo.add_blocks(state["job_id"], blocks)
        return state

    def _resolve_reading_order(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "resolve_reading_order")
            for block_id, order, needs_review in resolve_page_orders(repo.blocks(state["job_id"])):
                repo.update_block_reading_order(block_id, order, needs_review)
        return state

    def _remove_headers_footers(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "remove_headers_footers")
            blocks = repo.blocks(state["job_id"])
            repo.mark_blocks_header_footer(detect_header_footer_blocks(blocks, state.get("total_pages", 0)))
        return state

    def _classify_blocks(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "classify_blocks")
            for block in repo.blocks(state["job_id"]):
                repo.update_block_type(block.id, classify_block(block))
        return state

    def _protect_placeholders(self, state: PipelineState) -> PipelineState:
        # Placeholder mappings are persisted while chunks are built; this stage is explicit for workflow auditability.
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "protect_placeholders")
        return state

    def _extract_glossary(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "extract_glossary")
            terms = extract_term_candidates(repo.blocks(state["job_id"], include_headers=False))
            glossary_path = Path(state["output_dir"]) / "glossary.csv"
            write_glossary_csv(glossary_path, terms)
            repo.add_output(state["job_id"], "glossary_csv", glossary_path)
        return state

    def _build_chunks(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "build_chunks")
            if self.config.reset_chunks:
                logger.info("Resetting existing chunks/placeholders for job %s", state["job_id"])
                repo.delete_chunks_and_placeholders(state["job_id"])
            db_chunks = repo.chunks(state["job_id"])
            if not db_chunks:
                chunks, placeholders = build_chunks(repo.blocks(state["job_id"], include_headers=False), self.config.max_chunk_chars)
                repo.add_chunks(state["job_id"], chunks)
                for block_id, placeholder, original, kind in placeholders:
                    repo.add_placeholder(state["job_id"], block_id, None, placeholder, original, kind)
                db_chunks = repo.chunks(state["job_id"])
            state["chunks_total"] = len(db_chunks)
            state["chunks_done"] = len([c for c in db_chunks if c.status in {"validated", "needs_review", "failed"}])
            next_chunk = repo.next_pending_chunk(state["job_id"])
            state["current_chunk_id"] = next_chunk.id if next_chunk else None
            state["retry_count"] = next_chunk.retry_count if next_chunk else 0
            logger.info(
                "Prepared %s chunks; %s already complete; next chunk: %s",
                state["chunks_total"],
                state["chunks_done"],
                state["current_chunk_id"],
            )
        return state

    def _translate_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "translate_chunk")
            chunk = self._current_or_next_chunk(repo, state)
            if chunk is None:
                state["current_chunk_id"] = None
                return state
            state["current_chunk_id"] = chunk.id
            state["retry_count"] = chunk.retry_count
            state["validation_errors"] = []
            logger.info(
                "Translating chunk %s/%s pages %s-%s attempt %s",
                chunk.chunk_index,
                state.get("chunks_total", 0),
                chunk.page_start,
                chunk.page_end,
                chunk.retry_count + 1,
            )
            try:
                translation = translate_chunk(chunk, self.config.llm, strict_retry=chunk.retry_count > 0)
            except LLMClientError as exc:
                error = f"llm_error:{exc}"
                logger.warning("Chunk %s translation failed: %s", chunk.id, exc)
                repo.update_chunk_validation(chunk.id, "needs_retry", [error])
                state["validation_errors"] = [error]
                state["consecutive_llm_errors"] = state.get("consecutive_llm_errors", 0) + 1
                return state
            state["consecutive_llm_errors"] = 0
            repo.update_chunk_translation(chunk.id, translation)
        return state

    def _validate_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "validate_chunk")
            chunk = self._require_current_chunk(repo, state)
            result = validate_translation(chunk.source_text, chunk.protected_text, chunk.raw_translation or "")
            status = "validated" if result.passed else "needs_retry"
            repo.update_chunk_validation(chunk.id, status, result.errors)
            state["validation_errors"] = result.errors
            state["retry_count"] = chunk.retry_count
            if result.passed:
                logger.info("Validated chunk %s/%s", chunk.chunk_index, state.get("chunks_total", 0))
            else:
                logger.warning("Validation failed for chunk %s: %s", chunk.chunk_index, result.errors)
        return state

    def _retry_or_split_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "retry_or_split_chunk")
            chunk = self._require_current_chunk(repo, state)
            reason = retry_reason(chunk.validation_errors)
            state["retry_count"] = repo.increment_retry(state["job_id"], chunk.id, reason)
        return state

    def _meaning_check_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "meaning_check_chunk")
        return state

    def _terminology_check_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "terminology_check_chunk")
        return state

    def _russian_academic_post_edit(self, state: PipelineState) -> PipelineState:
        if not self.config.enable_post_edit:
            return state
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "russian_academic_post_edit")
            chunk = self._require_current_chunk(repo, state)
            edited = post_edit_translation(chunk.raw_translation or "", self.config.llm)
            chunk.edited_translation = edited
            chunk.status = "edited"
        return state

    def _final_validate_chunk(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "final_validate_chunk")
            chunk = self._require_current_chunk(repo, state)
            translation = chunk.edited_translation or chunk.raw_translation or ""
            result = validate_translation(chunk.source_text, chunk.protected_text, translation)
            repo.update_chunk_validation(chunk.id, "validated" if result.passed else "needs_review", result.errors)
            state["validation_errors"] = result.errors
        return state

    def _rebuild_pdf(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "rebuild_pdf")
            chunks = repo.chunks(state["job_id"])
            placeholder_map = {
                item.placeholder: item.original_text
                for item in repo.placeholders_for_job(state["job_id"])
            }
            txt_path = write_translated_text_from_chunks(
                Path(state["output_dir"]),
                chunks,
                placeholder_map=placeholder_map,
            )
            pdf_path = write_translated_pdf_from_chunks(
                Path(state["output_dir"]),
                chunks,
                placeholder_map=placeholder_map,
            )
            repo.add_output(state["job_id"], "translated_text", txt_path)
            repo.add_output(state["job_id"], "translated_pdf", pdf_path)
            final_outputs = state.get("final_outputs", {})
            final_outputs["translated_text"] = str(txt_path)
            final_outputs["translated_pdf"] = str(pdf_path)
            state["final_outputs"] = final_outputs
        return state

    def _generate_bilingual_review(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "generate_bilingual_review")
            path = generate_bilingual_review_placeholder(Path(state["output_dir"]))
            if path:
                repo.add_output(state["job_id"], "bilingual_review", path)
        return state

    def _generate_quality_report(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "generate_quality_report")
            path = generate_quality_report_placeholder(Path(state["output_dir"]))
            if path:
                repo.add_output(state["job_id"], "quality_report", path)
        return state

    def _finish_job(self, state: PipelineState) -> PipelineState:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            self._set_stage(repo, state, "finish_job")
            repo.update_job(state["job_id"], status="finished")
        return state

    def _current_or_next_chunk(self, repo: Repository, state: PipelineState) -> Chunk | None:
        chunk_id = state.get("current_chunk_id")
        chunk = repo.session.get(Chunk, chunk_id) if chunk_id else None
        if chunk and chunk.status in {"pending", "needs_retry"}:
            return chunk
        return repo.next_pending_chunk(state["job_id"])

    def _require_current_chunk(self, repo: Repository, state: PipelineState) -> Chunk:
        chunk_id = state.get("current_chunk_id")
        if not chunk_id:
            raise PipelineError("No current chunk is selected")
        chunk = repo.session.get(Chunk, chunk_id)
        if chunk is None:
            raise PipelineError(f"Chunk {chunk_id} not found")
        return chunk

    def _after_build_chunks(self, state: PipelineState) -> Literal["translate", "outputs"]:
        return "translate" if state.get("current_chunk_id") else "outputs"

    def _after_translation(self, state: PipelineState) -> Literal["validate", "retry", "next_chunk", "outputs"]:
        errors = state.get("validation_errors", [])
        if not errors:
            return "validate"
        if state.get("consecutive_llm_errors", 0) >= self.config.max_consecutive_llm_errors:
            raise PipelineError(
                "Too many consecutive local LLM failures/timeouts. "
                f"Stopped after {state['consecutive_llm_errors']} consecutive errors. "
                "Try --timeout 600, --max-chunk-chars 1500, and --reset-chunks, "
                "or check that the llama.cpp server is healthy."
            )
        if should_retry(errors, state.get("retry_count", 0), self.config.max_translation_attempts):
            return "retry"
        self._mark_current_needs_review(state)
        return self._select_next_or_outputs(state)

    def _after_validation(self, state: PipelineState) -> Literal["retry", "meaning_check", "post_edit", "next_chunk", "outputs"]:
        errors = state.get("validation_errors", [])
        if errors and should_retry(errors, state.get("retry_count", 0), self.config.max_translation_attempts):
            return "retry"
        if errors:
            self._mark_current_needs_review(state)
        elif self.config.enable_meaning_check:
            return "meaning_check"
        elif self.config.enable_post_edit:
            return "post_edit"
        return self._select_next_or_outputs(state)

    def _after_optional_checks(self, state: PipelineState) -> Literal["post_edit", "next_chunk", "outputs"]:
        if self.config.enable_post_edit:
            return "post_edit"
        return self._select_next_or_outputs(state)

    def _after_final_validation(self, state: PipelineState) -> Literal["next_chunk", "outputs"]:
        return self._select_next_or_outputs(state)

    def _select_next_or_outputs(self, state: PipelineState) -> Literal["next_chunk", "outputs"]:
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            next_chunk = repo.next_pending_chunk(state["job_id"])
            state["current_chunk_id"] = next_chunk.id if next_chunk else None
            if next_chunk:
                state["retry_count"] = next_chunk.retry_count
                return "next_chunk"
            chunks = repo.chunks(state["job_id"])
            state["chunks_done"] = len([c for c in chunks if c.status in {"validated", "needs_review", "failed"}])
            state["chunks_total"] = len(chunks)
            return "outputs"

    def _mark_current_needs_review(self, state: PipelineState) -> None:
        chunk_id = state.get("current_chunk_id")
        if not chunk_id:
            return
        with session_scope(self.session_factory) as session:
            repo = Repository(session)
            chunk = repo.session.get(Chunk, chunk_id)
            if chunk:
                repo.update_chunk_validation(chunk.id, "needs_review", chunk.validation_errors)
