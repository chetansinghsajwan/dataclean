from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame, PhoneCleaner

# ==============================================================================
# 1. CORE PROPERTIES & HEURISTICS
# ==============================================================================


def test_phone_cleaner_metadata():
    from dataclean.engine.dataframe import DataType

    cleaner = PhoneCleaner()
    assert cleaner.name == "PhoneCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR
    # Verify the new default configuration is an empty tuple
    assert cleaner.default_regions == ()


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("contact_no", 1.0),
        ("mobile_number", 1.0),
        ("user_tel", 1.0),
        ("office_fax", 1.0),
        ("email_address", 0.0),
    ],
)
def test_phone_cleaner_confidence(col_name, expected_confidence):
    cleaner = PhoneCleaner()
    mock_df = MagicMock(spec=DataFrame)
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. RESILIENT EXTRACTION & FORMATTING LOOPS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, default_regions, expected_output",
    [
        # --- E.164 Inputs (Self-Detecting, works perfectly with empty default_regions) ---
        ("+91 98765 43210", PhoneCleaner.Format.E164, (), "+919876543210"),
        ("+1-415-555-2671", PhoneCleaner.Format.E164, (), "+14155552671"),
        ("+44 20 7123 1234", PhoneCleaner.Format.E164, (), "+442071231234"),
        # --- Scientific Notation Recovery (Requires fallback since '+' is dropped) ---
        ("9.876543210E+09", PhoneCleaner.Format.E164, ("IN",), "+919876543210"),
        # --- Delimiter & Noise Purging (Requires fallback tuple) ---
        ("011-23456789", PhoneCleaner.Format.E164, ("IN",), "+911123456789"),
        (
            "(415) 555-2671",
            PhoneCleaner.Format.E164,
            ("US", "IN"),
            "+14155552671",
        ),  # Matches US first in the tuple
        # --- Regional & International Fallbacks ---
        ("9876543210", PhoneCleaner.Format.INTERNATIONAL, ("IN",), "+91 98765 43210"),
        ("9876543210", PhoneCleaner.Format.NATIONAL, ("IN",), "098765 43210"),
        ("9876543210", PhoneCleaner.Format.RAW_DIGITS, ("IN",), "919876543210"),
    ],
)
def test_phone_clean_value_success_matrix(
    input_val, out_fmt, default_regions, expected_output
):
    cleaner = PhoneCleaner(out_format=out_fmt, default_regions=default_regions)
    assert cleaner.clean_row(input_val) == expected_output


def test_phone_clean_empty_default_region_keeps_unjudgeable_local_numbers():
    # With no region known, a national-format number can't be validated, so it
    # is kept (stripped) rather than silently discarded.
    cleaner = PhoneCleaner()
    assert cleaner.clean_row("9876543210") == "9876543210"
    assert cleaner.clean_row("  011-23456789 ") == "011-23456789"

    # A number with an explicit '+' is self-contained and still gets cleaned.
    assert cleaner.clean_row("+91 98765 43210") == "+919876543210"


def test_phone_clean_known_region_still_drops_invalid_numbers():
    assert PhoneCleaner(default_regions=("IN",)).clean_row("12345") is None


def test_phone_country_context_selects_region():
    cleaner = PhoneCleaner()
    assert cleaner.clean_row("020 7357 8775", "United Kingdom") == "+442073578775"
    assert cleaner.clean_row("020 7357 8775", "GB") == "+442073578775"
    assert cleaner.clean_row("9876543210", "India") == "+919876543210"


def test_phone_country_context_is_tried_before_default_regions():
    cleaner = PhoneCleaner(default_regions=("IN",))
    assert cleaner.clean_row("020 7357 8775", "United Kingdom") == "+442073578775"


def test_phone_unknown_country_falls_back_to_default_regions():
    cleaner = PhoneCleaner(default_regions=("IN",))
    assert cleaner.clean_row("9876543210", "Atlantis") == "+919876543210"
    assert cleaner.clean_row("9876543210", "  ") == "+919876543210"
    # No usable country and no default region: unjudgeable, kept as-is.
    assert PhoneCleaner().clean_row("9876543210", "Atlantis") == "9876543210"


def test_phone_clean_value_invalid_returns_none():
    cleaner = PhoneCleaner(default_regions=("IN",))

    # 1. Truly malformed strings, missing digits, or arbitrary text drop out safely
    assert cleaner.clean_row("N/A") is None
    assert cleaner.clean_row("98765") is None  # Too short for a valid number
    assert cleaner.clean_row("This is completely random text") is None

    # 🚀 FIX 2: Acknowledge that the engine is powerful enough to extract phone numbers hidden inside text blobs!
    assert cleaner.clean_row("Call me at 9876543210") == "+919876543210"
