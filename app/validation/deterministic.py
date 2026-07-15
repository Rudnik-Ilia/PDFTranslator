import re
from dataclasses import dataclass

from app.pdf.placeholders import PLACEHOLDER_RE, missing_placeholders

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_WORD_RE = re.compile(r"\b[a-zA-Z]{4,}\b")
_MODEL_COMMENT_RE = re.compile(r"\b(here is|translation:|перевод:)\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![\w⟦])\d+(?:\.\d+)?")


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: list[str]


def validate_translation(source_text: str, protected_text: str, translation: str) -> ValidationResult:
    errors: list[str] = []
    if not translation.strip():
        errors.append("empty_translation")
    missing = missing_placeholders(protected_text, translation)
    if missing:
        errors.append("missing_placeholder:" + ",".join(missing))
    unprotected_source = PLACEHOLDER_RE.sub("", protected_text)
    source_numbers = set(_NUMBER_RE.findall(unprotected_source))
    translation_numbers = set(_NUMBER_RE.findall(translation))
    missing_numbers = sorted(source_numbers - translation_numbers)
    if missing_numbers:
        errors.append("missing_numbers:" + ",".join(missing_numbers[:20]))
    cyrillic_count = len(_CYRILLIC_RE.findall(translation))
    latin_count = len(_LATIN_WORD_RE.findall(translation))
    if cyrillic_count < max(20, latin_count * 2) and len(translation) > 80:
        errors.append("translation_not_mostly_russian")
    if _MODEL_COMMENT_RE.search(translation[:120]):
        errors.append("model_added_comment")
    source_len = max(len(source_text), 1)
    ratio = len(translation) / source_len
    if ratio < 0.25:
        errors.append("translation_too_short")
    if ratio > 3.5:
        errors.append("translation_too_long")
    if len(translation) > 100 and translation[: len(translation) // 2] == translation[len(translation) // 2 :]:
        errors.append("duplicated_output")
    return ValidationResult(passed=not errors, errors=errors)
