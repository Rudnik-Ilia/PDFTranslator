from __future__ import annotations

import re
from dataclasses import dataclass

PLACEHOLDER_RE = re.compile(r"⟦[A-Z_]+_\d{3,}⟧")


@dataclass(frozen=True)
class PlaceholderItem:
    placeholder: str
    original: str
    kind: str


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("URL", re.compile(r"https?://\S+")),
    ("DOI", re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)),
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("CITATION", re.compile(r"\[\d+(?:\s*,\s*\d+)*\]|\([A-Z][A-Za-z-]+ et al\., \d{4}\)")),
    ("FIG_REF", re.compile(r"\b(?:Fig\.|Figure)\s*\d+(?:\.\d+)?\b")),
    ("TABLE_REF", re.compile(r"\bTable\s*\d+(?:\.\d+)?\b")),
    ("SEC_REF", re.compile(r"\bSection\s*\d+(?:\.\d+)*\b")),
    ("NUMBER", re.compile(r"(?<![\w⟦])\d+(?:\.\d+)?(?:\s?%|\s?[A-Za-z]+/s|\s?(?:kg|g|mg|m|cm|mm|μm|nm|K|Hz|kHz|MHz|GHz|V|W|J|Pa))?")),
]

_FORMULA_HINT_RE = re.compile(r"[A-Za-z]\s*=|[=∑∫√≈≤≥±]")


def protect_text(text: str, start_index: int = 1) -> tuple[str, list[PlaceholderItem], int]:
    mappings: list[PlaceholderItem] = []
    counter = start_index
    protected = text

    def replace(kind: str, match: re.Match[str]) -> str:
        nonlocal counter
        placeholder = f"⟦{kind}_{counter:03d}⟧"
        counter += 1
        mappings.append(PlaceholderItem(placeholder=placeholder, original=match.group(0), kind=kind))
        return placeholder

    if _FORMULA_HINT_RE.search(protected) and len(protected) < 240:
        placeholder = f"⟦FORMULA_{counter:03d}⟧"
        counter += 1
        return placeholder, [PlaceholderItem(placeholder, protected, "FORMULA")], counter

    for kind, pattern in _PATTERNS:
        protected = pattern.sub(lambda match, k=kind: replace(k, match), protected)
    return protected, mappings, counter


def restore_placeholders(text: str, mappings: list[PlaceholderItem]) -> str:
    restored = text
    for item in mappings:
        restored = restored.replace(item.placeholder, item.original)
    return restored


def missing_placeholders(source_protected_text: str, translated_text: str) -> list[str]:
    expected = set(PLACEHOLDER_RE.findall(source_protected_text))
    actual = set(PLACEHOLDER_RE.findall(translated_text))
    return sorted(expected - actual)
