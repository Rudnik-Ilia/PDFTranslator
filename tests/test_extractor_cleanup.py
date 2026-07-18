from app.pdf.extractor import collapse_adjacent_duplicate_words


def test_collapse_short_pdf_title_duplicates() -> None:
    assert collapse_adjacent_duplicate_words("Science Science") == "Science"
    assert collapse_adjacent_duplicate_words("AND AND Development Development") == "AND Development"
    assert collapse_adjacent_duplicate_words("OF OF Muscle Muscle Hypertrophy Hypertrophy") == "OF Muscle Hypertrophy"


def test_does_not_rewrite_long_prose() -> None:
    text = "This is a normal sentence that that can occur in prose when quoting speech. " * 4
    assert collapse_adjacent_duplicate_words(text) == text
