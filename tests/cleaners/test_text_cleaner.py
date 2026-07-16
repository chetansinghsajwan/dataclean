import math

import pytest
from unittest.mock import MagicMock

from dataclean.cleaners.text_cleaner import TextCleaner

# ==============================================================================
# 1. CORE PROPERTIES & SCHEMA VERIFICATION
# ==============================================================================


def test_text_cleaner_metadata():
    cleaner = TextCleaner()
    assert cleaner.name() == "TextCleaner"
    assert cleaner.output_schema() == "str"


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
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


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
    assert cleaner.clean_value(input_val) == expected_output


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
    assert cleaner.clean_value(messy_string) == expected


# ==============================================================================
# 4. EDGE CASES & SAFE FALLBACKS
# ==============================================================================


def test_text_clean_value_invalid_returns_none():
    cleaner = TextCleaner()

    # 1. Non-string database structures drop out safely without crashing the pipeline
    assert cleaner.clean_value(None) is None
    assert cleaner.clean_value(math.nan) is None
    assert cleaner.clean_value(12345) is None


def test_text_clean_value_empty_after_cleaning_returns_none():
    cleaner = TextCleaner(remove_html=True, remove_digits=True, remove_punctuation=True)

    # 2. Strings that are entirely reduced to nothing by the pipeline should resolve to None
    assert cleaner.clean_value("<p></p>") is None
    assert cleaner.clean_value("12345") is None
    assert cleaner.clean_value("!!! ???") is None
    assert cleaner.clean_value("   \n \t  ") is None
