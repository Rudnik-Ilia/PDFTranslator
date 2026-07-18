from pydantic import BaseModel

from app.llm.llm_client import LLMClient


class TranslationRequest(BaseModel):
    source_lang_code: str
    target_lang_code: str
    text: str


class TranslationService:
    def __init__(self, *, client: LLMClient, system_prompt: str) -> None:
        self.client = client
        self.system_prompt = system_prompt

    def translate(self, request: TranslationRequest) -> str | None:
        user_prompt = (
            f"Source language: {request.source_lang_code}\n"
            f"Target language: {request.target_lang_code}\n\n"
            f"Text:\n{request.text}"
        )

        return self.client.chat(system_prompt=self.system_prompt, user_prompt=user_prompt)
