from app.core.config import LLMConfig
from app.llm.llm_client import OpenAICompatibleClient
from app.llm.prompts import MEANING_CHECK_PROMPT


def meaning_check(source_text: str, translation: str, llm_config: LLMConfig) -> str | None:
    client = OpenAICompatibleClient(llm_config)
    return client.chat(system_prompt="You are a strict bilingual scientific translation reviewer.", user_prompt=MEANING_CHECK_PROMPT.format(source_text=source_text, translation=translation))
