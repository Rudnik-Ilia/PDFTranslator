TRANSLATION_SYSTEM_PROMPT = "You are a precise scientific English-to-Russian translator."

TRANSLATION_USER_PROMPT = """You are translating a scientific book from English to Russian.

Rules:
* Translate into accurate Russian academic style.
* Preserve all placeholders exactly.
* Use the glossary exactly.
* Do not translate formulas, citations, URLs, DOI, code, model names, dataset names.
* Do not add explanations.
* Do not summarize.
* Do not omit information.
* Return only the Russian translation.

Domain:
{domain}

Glossary:
{glossary}

Chapter context:
{chapter_summary}

Previous paragraph:
{previous_translated_paragraph}

Text:
{protected_text}
"""

STRICT_RETRY_SUFFIX = """

Previous attempt failed validation. Strictly preserve every placeholder token exactly as written. Return only the corrected Russian translation.
"""

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
