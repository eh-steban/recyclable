"""Tests for the quote normalizer (pure domain, no DB)."""

from src.domain.quote_normalize import normalize

# ---- Curly single quotes ----


def test_curly_left_single_quote_replaced():
    assert normalize("it's fine") == "it's fine"


def test_curly_right_single_quote_replaced():
    assert normalize("it's fine") == "it's fine"


def test_both_curly_single_quotes_replaced():
    assert normalize("'hello'") == "'hello'"


# ---- Curly double quotes ----


def test_curly_left_double_quote_replaced():
    assert normalize("“hello") == '"hello'


def test_curly_right_double_quote_replaced():
    assert normalize("hello”") == 'hello"'


def test_both_curly_double_quotes_replaced():
    assert normalize("“hello world”") == '"hello world"'


# ---- Non-breaking space ----


def test_nbsp_replaced_with_space():
    # U+00A0 non-breaking space
    assert normalize("aluminum cans") == "aluminum cans"


def test_multiple_nbsp_collapsed():
    # NBSP + space -> single space after collapse
    assert normalize("a  b") == "a b"


# ---- Whitespace collapse ----


def test_multiple_spaces_collapsed():
    assert normalize("a  b   c") == "a b c"


def test_newline_collapsed_to_space():
    assert normalize("line one\nline two") == "line one line two"


def test_tab_collapsed_to_space():
    assert normalize("col1\tcol2") == "col1 col2"


def test_mixed_whitespace_collapsed():
    assert normalize("a \n\t b") == "a b"


# ---- Trim ----


def test_leading_whitespace_trimmed():
    assert normalize("  hello") == "hello"


def test_trailing_whitespace_trimmed():
    assert normalize("hello  ") == "hello"


def test_both_ends_trimmed():
    assert normalize("  hello  ") == "hello"


def test_empty_string_returns_empty():
    assert normalize("") == ""


def test_whitespace_only_returns_empty():
    assert normalize("   \n\t  ") == ""


# ---- Round-trip / substring property ----


def test_straight_quote_unchanged():
    """Straight quotes should pass through unmodified."""
    s = 'it\'s "fine"'
    assert normalize(s) == s


def test_normalization_is_idempotent():
    """Applying normalize twice should produce the same result as once."""
    raw = "  “Hello World”\n"
    once = normalize(raw)
    twice = normalize(once)
    assert once == twice


def test_substring_after_normalization():
    """Simulates the quote-integrity check used by the seed loader."""
    source_text = (
        "Denver residents may recycle “aluminum cans” in their curbside bin."
    )
    quote = "“aluminum cans” in their curbside bin"
    assert normalize(quote) in normalize(source_text)


def test_substring_fails_for_unrelated_text():
    """Text that is genuinely absent should not match after normalization."""
    source_text = "Aluminum cans are accepted."
    quote = "Plastic bags are not accepted."
    assert normalize(quote) not in normalize(source_text)


def test_curly_quote_variant_matches_straight_quote_source():
    """A quote with curly quotes should match a source with straight quotes."""
    source_text = 'Place "aluminum cans" in the blue bin.'
    quote = "“aluminum cans” in the blue bin"
    assert normalize(quote) in normalize(source_text)
