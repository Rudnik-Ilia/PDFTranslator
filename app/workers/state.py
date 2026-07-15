from typing import TypedDict


class PipelineState(TypedDict):
    job_id: int
    input_pdf_path: str
    output_dir: str
    current_stage: str
    total_pages: int
    current_chunk_id: int | None
    chunks_total: int
    chunks_done: int
    retry_count: int
    validation_errors: list[str]
    consecutive_llm_errors: int
    final_outputs: dict[str, str]
