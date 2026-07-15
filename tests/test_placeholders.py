from app.pdf.placeholders import missing_placeholders, protect_text, restore_placeholders


def test_protect_and_restore_url_citation_and_number() -> None:
    text = "See Fig. 4.2 and [17] at https://example.com with 42 kg."
    protected, mappings, _ = protect_text(text)
    assert "⟦FIG_REF_" in protected
    assert "⟦CITATION_" in protected
    assert "⟦URL_" in protected
    assert "⟦NUMBER_" in protected
    assert restore_placeholders(protected, mappings) == text


def test_missing_placeholders() -> None:
    source = "A ⟦URL_001⟧ B ⟦CITATION_002⟧"
    translated = "А ⟦URL_001⟧ Б"
    assert missing_placeholders(source, translated) == ["⟦CITATION_002⟧"]
