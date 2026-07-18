from __future__ import annotations

import logging
from typing import Protocol

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)

from app.core.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """Raised when communication with an LLM provider fails."""


class LLMClient(Protocol):
    def chat(self, *, system_prompt: str, user_prompt: str) -> str | None:
        """Send a chat request and return plain text."""

    def close(self) -> None:
        """Release network resources."""


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        api_key = config.openrouter_api_key.get_secret_value() or "llama-cpp-local"
        self._client = OpenAI(
            api_key=api_key,
            base_url=str(config.base_url).rstrip("/"),
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def __enter__(self) -> OpenAICompatibleClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def chat(self, *, system_prompt: str, user_prompt: str) -> str | None:
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            )
        except APITimeoutError as exc:
            raise LLMClientError(f"LLM request timed out after {self.config.timeout}s" ) from exc
        except APIStatusError as exc:
            request_id = getattr(exc, "request_id", None)
            request_info = f", request_id={request_id}" if request_id else ""

            raise LLMClientError(f"LLM server returned HTTP {exc.status_code} {request_info}: {exc}") from exc
        except APIConnectionError as exc:
            raise LLMClientError(f"Could not connect to LLM server at {self.config.base_url}: {exc}") from exc
        except APIError as exc:
            raise LLMClientError(f"LLM SDK request failed: {exc}") from exc

        if not response.choices:
            logger.debug("LLM returned no choices: %r", response)
            raise LLMClientError("LLM response contained no choices")

        content = response.choices[0].message.content

        if not isinstance(content, str):
            logger.debug("Unexpected LLM response content: %r", content)
            raise LLMClientError("LLM response content was not text")

        result = content.strip()

        if not result:
            raise LLMClientError("LLM returned an empty response")

        return result
