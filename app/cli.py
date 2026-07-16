from pathlib import Path
from typing import Annotated

import typer

from app.core.config import Configuration, LLMConfig, PipelineConfig
from app.core.logging import configure_logging
from app.db.repository import Repository
from app.db.session import create_session_factory, session_scope
from app.output.pdf_builder import (
    write_translated_pdf_from_chunks,
    write_translated_text_from_chunks,
)
from app.pdf.analyzer import SCANNED_PDF_MESSAGE
from app.workers.pipeline import PDFTranslationPipeline, PipelineError

app = typer.Typer(help="PDF-only English-to-Russian scientific document translator.", no_args_is_help=True)


@app.callback()
def root() -> None:
    """PDF-only English-to-Russian scientific document translator."""


@app.command()
def translate(
    input: Annotated[Path, typer.Option("--input", "-i", help="Input text-based English PDF.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory for translated PDF.")],
    backend: Annotated[str, typer.Option(help="LLM backend. MVP supports llama_cpp OpenAI-compatible API.")] = "llama_cpp",
    base_url: Annotated[str, typer.Option(help="OpenAI-compatible base URL, e.g. http://localhost:8888/v1")] = "http://localhost:8888/v1",
    model: Annotated[str, typer.Option(help="Model name sent to OpenAI-compatible API.")] = "local-model",
    temperature: Annotated[float, typer.Option(help="LLM temperature.")] = 0.1,
    max_tokens: Annotated[int, typer.Option(help="Maximum output tokens per request.")] = 4096,
    timeout: Annotated[float, typer.Option(help="LLM request timeout in seconds.")] = 120.0,
    max_translation_attempts: Annotated[int, typer.Option(help="Maximum attempts per chunk before needs_review.")] = 3,
    max_consecutive_llm_errors: Annotated[int, typer.Option(help="Abort after this many consecutive LLM transport failures/timeouts.")] = 5,
    max_chunk_chars: Annotated[int, typer.Option(help="Approximate maximum protected characters per chunk.")] = 4500,
    reset_chunks: Annotated[bool, typer.Option(help="Delete existing chunks/placeholders and rebuild them with current chunk settings.")] = False,
    enable_post_edit: Annotated[bool, typer.Option(help="Run optional Russian academic post-editing stage.")] = False,
    enable_meaning_check: Annotated[bool, typer.Option(help="Run optional LLM meaning check for validated chunks.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Translate a text-based scientific PDF into Russian using a local LLM."""
    configure_logging(verbose)
    if backend != "llama_cpp":
        raise typer.BadParameter("MVP supports only backend=llama_cpp")
    config: Configuration = PipelineConfig(
        input_pdf_path=input,
        output_dir=output,
        max_chunk_chars=max_chunk_chars,
        max_translation_attempts=max_translation_attempts,
        max_consecutive_llm_errors=max_consecutive_llm_errors,
        reset_chunks=reset_chunks,
        enable_post_edit=enable_post_edit,
        enable_meaning_check=enable_meaning_check,
        llm=LLMConfig(backend=backend, base_url=base_url, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout))
    try:
        final_state = PDFTranslationPipeline(config).run()
    except PipelineError as exc:
        if str(exc) == SCANNED_PDF_MESSAGE:
            typer.echo(SCANNED_PDF_MESSAGE, err=True)
            raise typer.Exit(code=2) from exc
        typer.echo(f"Pipeline failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Pipeline failed unexpectedly: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Translation pipeline finished.")
    for kind, path in final_state.get("final_outputs", {}).items():
        typer.echo(f"{kind}: {path}")


@app.command()
def export(
    output: Annotated[Path, typer.Option("--output", "-o", help="Existing output/job directory containing project_state.sqlite.")],
    include_missing_markers: Annotated[bool, typer.Option(help="Include visible placeholders for chunks that are not translated yet.")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Generate translated_ru.txt and translated_ru.pdf from the current SQLite state."""
    configure_logging(verbose)
    db_path = output / "project_state.sqlite"
    if not db_path.exists():
        typer.echo(f"State database not found: {db_path}", err=True)
        raise typer.Exit(code=1)
    factory = create_session_factory(output)
    try:
        with session_scope(factory) as session:
            repo = Repository(session)
            job = repo.latest_job()
            chunks = repo.chunks(job.id)
            if not chunks:
                typer.echo("No chunks found. Run translate first.", err=True)
                raise typer.Exit(code=1)
            placeholder_map = {
                item.placeholder: item.original_text
                for item in repo.placeholders_for_job(job.id)
            }
            txt_path = write_translated_text_from_chunks(output, chunks, include_missing_markers=include_missing_markers, placeholder_map=placeholder_map)
            pdf_path = write_translated_pdf_from_chunks(output, chunks, include_missing_markers=include_missing_markers, placeholder_map=placeholder_map, title="Russian Translation Draft")
            repo.add_output(job.id, "translated_text", txt_path)
            repo.add_output(job.id, "translated_pdf", pdf_path)
            translated = len([c for c in chunks if (c.edited_translation or c.raw_translation or "").strip()])
            typer.echo("Export finished.")
            typer.echo(f"chunks with translation: {translated}/{len(chunks)}")
            typer.echo(f"translated_text: {txt_path}")
            typer.echo(f"translated_pdf: {pdf_path}")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Export failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def main() -> None:
    app()
