from app.validation.deterministic import validate_translation


def test_validation_passes_for_russian_with_placeholder_and_number() -> None:
    result = validate_translation(
        "Energy is 42 J [17].",
        "Energy is ⟦NUMBER_001⟧ J ⟦CITATION_002⟧.",
        "Энергия составляет ⟦NUMBER_001⟧ J ⟦CITATION_002⟧.",
    )
    assert result.passed


def test_validation_detects_missing_placeholder() -> None:
    result = validate_translation("See [17].", "See ⟦CITATION_001⟧.", "См. ссылку.")
    assert not result.passed
    assert any(error.startswith("missing_placeholder") for error in result.errors)
