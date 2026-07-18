from app.core.config import LLMConfig
from app.llm.llm_client import OpenAICompatibleClient

POST_EDIT_SYSTEM_PROMPT = "You are a Russian scientific editor."
POST_EDIT_USER_PROMPT = """Edit this Russian scientific translation.

Rules:
* Improve academic Russian style.
* Do not change meaning.
* Do not remove placeholders.
* Do not add explanations.
* Preserve citations, formulas, numbers, units.
* Return only edited Russian text.

Text:
{translation}
"""


def post_edit_translation(translation: str, llm_config: LLMConfig) -> str:
    client = OpenAICompatibleClient(llm_config)
    return client.chat(system_prompt=POST_EDIT_SYSTEM_PROMPT, user_prompt=POST_EDIT_USER_PROMPT.format(translation=translation))
