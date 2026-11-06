from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame, TextCleaner

# ==============================================================================
# 1. CORE PROPERTIES & SCHEMA VERIFICATION
# ==============================================================================


def test_text_cleaner_metadata():
    from dataclean.engine.dataframe import DataType

    cleaner = TextCleaner()
    assert cleaner.name == "TextCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("user_comment", 0.8),
        ("product_description", 0.8),
        ("order_notes", 0.8),
        ("review_text", 0.8),
        ("first_name", 0.1),  # Generic string fallback
    ],
)
def test_text_cleaner_confidence(col_name, expected_confidence):
    cleaner = TextCleaner()
    mock_df = MagicMock(spec=DataFrame)
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. INDIVIDUAL PIPELINE TOGGLE VERIFICATION
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, kwargs, expected_output",
    [
        # --- HTML Stripping ---
        ("<p>Hello</p> World", {"remove_html": True}, "hello world"),
        ("<p>Hello</p> World", {"remove_html": False}, "<p>hello</p> world"),
        # --- URL Stripping ---
        ("Check https://google.com for info", {"remove_urls": True}, "check for info"),
        ("Visit www.site.org now", {"remove_urls": True}, "visit now"),
        # --- Email Stripping ---
        ("Email admin@company.com today", {"remove_emails": True}, "email today"),
        # --- Digit Stripping ---
        ("Order 12345 is ready", {"remove_digits": True}, "order is ready"),
        ("Order 12345 is ready", {"remove_digits": False}, "order 12345 is ready"),
        # --- Punctuation Stripping ---
        (
            "Hello, world! How are you?",
            {"remove_punctuation": True},
            "hello world how are you",
        ),
        # --- Newline Management ---
        ("Line 1\nLine 2", {"replace_newlines_with_spaces": True}, "line 1 line 2"),
        ("Line 1\nLine 2", {"replace_newlines_with_spaces": False}, "line 1line 2"),
        # --- Casing Management ---
        ("LOUD NOISES", {"lowercase": True}, "loud noises"),
        ("LOUD NOISES", {"lowercase": False}, "LOUD NOISES"),
        # --- Whitespace Collapse (Always Active) ---
        ("Too    much \t space", {}, "too much space"),
    ],
)
def test_text_clean_value_toggles(input_val, kwargs, expected_output):
    # Initialize the cleaner with the specific test overrides, relying on default frozen rules otherwise
    cleaner = TextCleaner(**kwargs)
    assert cleaner.clean_row(input_val) == expected_output


# ==============================================================================
# 3. COMBINED PIPELINE EXECUTION
# ==============================================================================


def test_text_clean_combined_pipeline():
    """Validates that the linear execution pipeline correctly handles a deeply contaminated string."""
    messy_string = "<p>Contact admin@test.com or visit https://site.com. Invoice #9988 is attached!</p>\nThank you."

    cleaner = TextCleaner(
        remove_html=True,
        remove_urls=True,
        remove_emails=True,
        remove_digits=True,
        remove_punctuation=True,
        replace_newlines_with_spaces=True,
        lowercase=True,
    )

    # The pipeline should systematically strip out HTML, emails, URLs, digits, punctuation, and newlines in sequence
    expected = "contact or visit invoice is attached thank you"
    assert cleaner.clean_row(messy_string) == expected


# ==============================================================================
# 4. EDGE CASES & SAFE FALLBACKS
# ==============================================================================


# def test_text_clean_value_invalid_returns_none():
#     cleaner = TextCleaner()

#     # 1. Non-string database structures drop out safely without crashing the pipeline
#     assert cleaner.clean_row(None) is None
#     assert cleaner.clean_row(math.nan) is None
#     assert cleaner.clean_row(12345) is None


def test_text_clean_value_empty_after_cleaning_returns_none():
    cleaner = TextCleaner(remove_html=True, remove_digits=True, remove_punctuation=True)

    # 2. Strings that are entirely reduced to nothing by the pipeline should resolve to None
    assert cleaner.clean_row("<p></p>") is None
    assert cleaner.clean_row("12345") is None
    assert cleaner.clean_row("!!! ???") is None
    assert cleaner.clean_row("   \n \t  ") is None


# ==============================================================================
# 5. HTML ENTITIES, PLACEHOLDER TOKENS AND DEFAULTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, kwargs, expected_output",
    [
        ("a &amp; b", {}, "a & b"),
        ("it&#39;s &quot;ok&quot;", {}, 'it\'s "ok"'),
        ("caf&eacute;&nbsp;bar", {}, "café bar"),
        ("<b>a &amp; b</b>", {}, "a & b"),
        # Only entities that end with a semicolon are decoded.
        ("AT&T and R&D", {}, "at&t and r&d"),
        ("x&notify", {}, "x&notify"),
        ("a &amp; b", {"decode_entities": False}, "a &amp; b"),
    ],
)
def test_text_clean_decodes_entities(input_val, kwargs, expected_output):
    assert TextCleaner(**kwargs).clean_row(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val",
    ["null", "NULL", "None", "NaN", "undefined", "n/a", "N/A", "na", "-", "  -  "],
)
def test_text_clean_placeholder_tokens_become_none(input_val):
    assert TextCleaner().clean_row(input_val) is None


@pytest.mark.parametrize("input_val", ["Infinity", "inf", "-Infinity", "+inf"])
def test_text_clean_infinity_is_placeholder_by_default(input_val):
    assert TextCleaner().clean_row(input_val) is None
    assert TextCleaner(infinity_as_null=False).clean_row(input_val) == (
        input_val.lower()
    )


def test_text_clean_placeholder_only_matches_whole_value():
    cleaner = TextCleaner()
    assert cleaner.clean_row("none of the above") == "none of the above"
    assert cleaner.clean_row("n/a for now") == "n/a for now"


def test_text_clean_custom_null_tokens_replace_defaults():
    cleaner = TextCleaner(null_tokens=("tbd",))
    assert cleaner.clean_row("TBD") is None
    assert cleaner.clean_row("null") == "null"


def test_text_clean_defaults_pin_html_and_lowercase():
    cleaner = TextCleaner()
    assert cleaner.clean_row("<script>alert(1)</script>") == "alert(1)"
    assert cleaner.clean_row("Called back; wants QUOTE") == "called back; wants quote"
    assert TextCleaner(remove_html=False).clean_row("<b>x</b>") == "<b>x</b>"


@pytest.mark.parametrize(
    "input_val, kwargs, expected_output",
    [
        ("a​b", {}, "ab"),
        ("﻿bom start", {}, "bom start"),
        ("join⁠ed", {}, "joined"),
        ("​﻿", {}, None),
        ("a​b", {"remove_invisible": False}, "a​b"),
        # Joiners carry meaning in Indic scripts and emoji, so they stay.
        ("क्‍ष", {}, "क्‍ष"),
        ("\U0001f468‍\U0001f469", {}, "\U0001f468‍\U0001f469"),
    ],
)
def test_text_clean_invisible_characters(input_val, kwargs, expected_output):
    assert TextCleaner(**kwargs).clean_row(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val, kwargs, expected_output",
    [
        ("café", {}, "café"),
        ("Nguyễn", {}, "nguyễn"),
        ("café", {}, "café"),
        # Entities that decode to a combining mark are composed afterwards.
        ("cafe&#769;", {}, "café"),
        ("café", {"normalize_unicode": False}, "café"),
    ],
)
def test_text_clean_normalizes_unicode_to_nfc(input_val, kwargs, expected_output):
    assert TextCleaner(**kwargs).clean_row(input_val) == expected_output


# ==============================================================================
# 6. SAFE DEFAULTS FOR URLS, EMAILS, COMPARISONS, QUOTES AND STACKED MARKS
# ==============================================================================


def test_text_clean_keeps_urls_and_emails_by_default():
    cleaner = TextCleaner()
    assert cleaner.clean_row("see www.example.com") == "see www.example.com"
    assert cleaner.clean_row("mail a@b.com now") == "mail a@b.com now"


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("if a < b and c > d", "if a < b and c > d"),
        ("3 < 5 > 2", "3 < 5 > 2"),
        ("x<5 and y>3", "x<5 and y>3"),
        ("<p>Hello</p> World", "hello world"),
        ('<a href="x">link</a>', "link"),
        ("a<br/>b", "a b"),
        ("<!-- note -->kept", "kept"),
        ("<!DOCTYPE html>text", "text"),
    ],
)
def test_text_clean_html_only_strips_real_tags(input_val, expected_output):
    assert TextCleaner().clean_row(input_val) == expected_output


@pytest.mark.parametrize("input_val", ["''", '""', "  ''  "])
def test_text_clean_empty_quotes_become_none(input_val):
    assert TextCleaner().clean_row(input_val) is None


def test_text_clean_limits_stacked_combining_marks():
    zalgo = "Z͈͛͡alg̃o"
    assert TextCleaner().clean_row(zalgo) == "z͈͛alg̃o"
    assert TextCleaner(max_combining_marks=None).clean_row(zalgo) == zalgo.lower()
    assert TextCleaner(max_combining_marks=0).clean_row(zalgo) == "zalgo"


def test_text_clean_combining_marks_keep_normal_scripts():
    cleaner = TextCleaner()
    # Composed accents, Vietnamese tone marks, Indic vowel signs and Arabic
    # with two marks all stay intact.
    for text in ("café", "nguyễn", "हिन्दी"):
        assert cleaner.clean_row(text) == text
    # NFC reorders the two Arabic marks into canonical order but keeps both.
    assert cleaner.clean_row("\u0628\u0651\u064e") == "\u0628\u064e\u0651"


# ==============================================================================
# 7. SYMBOL AND NUMBER REMOVAL (OFF BY DEFAULT)
# ==============================================================================


def test_text_clean_symbols_and_numbers_are_kept_by_default():
    cleaner = TextCleaner()
    assert cleaner.clean_row("Pay $5 + 3 © \U0001f600") == "pay $5 + 3 © \U0001f600"


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        ("Pay $5 + 3 = 8", "pay 5 3 8"),
        ("£1,000 ₹500", "1,000 500"),
        ("hello \U0001f600 world ©", "hello world"),
        # Punctuation is not a symbol, so it stays.
        ("Hello, world! (ok)", "hello, world! (ok)"),
        ("a<b>c", "abc"),
    ],
)
def test_text_clean_remove_symbols(input_val, expected_output):
    assert (
        TextCleaner(remove_symbols=True, remove_html=False).clean_row(input_val)
        == expected_output
    )


def test_text_clean_remove_digits_strips_numbers():
    cleaner = TextCleaner(remove_digits=True)
    assert cleaner.clean_row("Order 12345 is ready") == "order is ready"
    assert cleaner.clean_row("१२३ abc") == "abc"
