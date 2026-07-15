from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class LLMConfig(BaseModel):
    backend: str = "llama_cpp"
    base_url: HttpUrl | str = Field(default="http://10.100.102.5:8888/v1")
    model: str = "local-model"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: float = 120.0
    max_retries: int = 2


class PipelineConfig(BaseModel):
    input_pdf_path: Path
    output_dir: Path
    llm: LLMConfig
    max_chunk_chars: int = 4500
    min_text_chars_for_text_pdf: int = 200
    max_translation_attempts: int = 3
    max_consecutive_llm_errors: int = 5
    reset_chunks: bool = False
    enable_meaning_check: bool = False
    enable_post_edit: bool = False
