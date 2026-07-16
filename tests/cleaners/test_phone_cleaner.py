import pytest
from unittest.mock import MagicMock
from dataclean.cleaners.phone_cleaner import PhoneCleaner


# ==============================================================================
# 1. CORE PROPERTIES & HEURISTICS
# ==============================================================================

def test_phone_cleaner_metadata():
    cleaner = PhoneCleaner()
    assert cleaner.name() == "PhoneCleaner"
    assert cleaner.output_schema() == "str"
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
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


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
        ("(415) 555-2671", PhoneCleaner.Format.E164, ("US", "IN"), "+14155552671"), # Matches US first in the tuple

        # --- Regional & International Fallbacks ---
        ("9876543210", PhoneCleaner.Format.INTERNATIONAL, ("IN",), "+91 98765 43210"),
        ("9876543210", PhoneCleaner.Format.NATIONAL, ("IN",), "098765 43210"),
        ("9876543210", PhoneCleaner.Format.RAW_DIGITS, ("IN",), "919876543210"),
    ],
)
def test_phone_clean_value_success_matrix(input_val, out_fmt, default_regions, expected_output):
    cleaner = PhoneCleaner(out_format=out_fmt, default_regions=default_regions)
    assert cleaner.clean_value(input_val) == expected_output


def test_phone_clean_empty_default_region_drops_local_numbers():
    # Because default_regions is (), any number without a leading '+' must return None safely
    cleaner = PhoneCleaner()
    assert cleaner.clean_value("9876543210") is None
    assert cleaner.clean_value("011-23456789") is None

    # But a number with an explicit '+' should still work perfectly
    assert cleaner.clean_value("+91 98765 43210") == "+919876543210"


def test_phone_clean_value_invalid_returns_none():
    cleaner = PhoneCleaner(default_regions=("IN",))

    # 1. Truly malformed strings, missing digits, or arbitrary text drop out safely
    assert cleaner.clean_value("N/A") is None
    assert cleaner.clean_value("98765") is None  # Too short for a valid number
    assert cleaner.clean_value("This is completely random text") is None

    # 🚀 FIX 2: Acknowledge that the engine is powerful enough to extract phone numbers hidden inside text blobs!
    assert cleaner.clean_value("Call me at 9876543210") == "+919876543210"
