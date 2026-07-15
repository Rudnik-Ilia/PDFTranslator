from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        url = str(self.config.base_url).rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMClientError(f"LLM request timed out after {self.config.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc
        except ValueError as exc:
            raise LLMClientError("LLM response was not valid JSON") from exc
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.debug("Unexpected LLM response: %s", data)
            raise LLMClientError("LLM response did not contain choices[0].message.content") from exc
