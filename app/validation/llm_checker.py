from app.core.config import LLMConfig
from app.translation.llm_client import OpenAICompatibleClient

MEANING_CHECK_PROMPT = """Compare English source and Russian translation.

Find only serious issues:
* omitted information
* added information
* changed meaning
* wrong negation
* wrong quantity
* wrong relation
* mistranslated scientific term

Return JSON with has_critical_issue and issues.

English:
{source_text}

Russian:
{translation}
"""


def meaning_check(source_text: str, translation: str, llm_config: LLMConfig) -> str:
    client = OpenAICompatibleClient(llm_config)
    return client.chat(system_prompt="You are a strict bilingual scientific translation reviewer.", user_prompt=MEANING_CHECK_PROMPT.format(source_text=source_text, translation=translation))
