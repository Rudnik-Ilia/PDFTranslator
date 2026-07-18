from app.core.config import LLMConfig
from app.db.models import Chunk
from app.llm.llm_client import OpenAICompatibleClient
from app.llm.prompts import (
    STRICT_RETRY_SUFFIX,
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_USER_PROMPT,
)


def translate_chunk(chunk: Chunk, llm_config: LLMConfig, *, strict_retry: bool = False) -> str | None:
    client = OpenAICompatibleClient(llm_config)
    prompt = TRANSLATION_USER_PROMPT.format(
        domain="scientific and technical book",
        glossary="No approved glossary terms provided in MVP.",
        chapter_summary="",
        previous_translated_paragraph="",
        protected_text=chunk.protected_text,
    )
    if strict_retry:
        prompt += STRICT_RETRY_SUFFIX
    return client.chat(system_prompt=TRANSLATION_SYSTEM_PROMPT, user_prompt=prompt)
