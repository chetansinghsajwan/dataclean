from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.bool_cleaner import BoolCleaner

# ==============================================================================
# 1. CORE METADATA & DATA TYPE HEURISTICS
# ==============================================================================


def test_boolean_cleaner_metadata():
    cleaner = BoolCleaner(out_format=BoolCleaner.Format.TRUEFALSE)
    assert cleaner.name() == "BoolCleaner"
    assert cleaner.output_schema() == "bool"

    str_cleaner = BoolCleaner(out_format=BoolCleaner.Format.YESNO)
    assert str_cleaner.output_schema() == "str"


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("is_approved", 1.0),
        ("has_premium", 1.0),
        ("user_status", 1.0),
        ("active_flag", 1.0),
        ("first_name", 0.0),
        ("email_address", 0.0),
    ],
)
def test_boolean_cleaner_confidence(col_name, expected_confidence):
    cleaner = BoolCleaner()
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. DATA COERCION AND TRANSFORMATION MAPPING LOOPS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Native Boolean Outputs ---
        ("True", BoolCleaner.Format.TRUEFALSE, True),
        ("yes", BoolCleaner.Format.TRUEFALSE, True),
        ("1", BoolCleaner.Format.TRUEFALSE, True),
        ("False", BoolCleaner.Format.TRUEFALSE, False),
        ("no", BoolCleaner.Format.TRUEFALSE, False),
        ("0", BoolCleaner.Format.TRUEFALSE, False),
        # --- Numeric String Flag Outputs ---
        ("true", BoolCleaner.Format.BINARY, "1"),
        ("active", BoolCleaner.Format.BINARY, "1"),
        ("false", BoolCleaner.Format.BINARY, "0"),
        ("inactive", BoolCleaner.Format.BINARY, "0"),
        # --- Standardized Text Outputs ---
        ("T", BoolCleaner.Format.YESNO, "Yes"),
        ("Y", BoolCleaner.Format.YESNO, "Yes"),
        ("F", BoolCleaner.Format.YESNO, "No"),
        ("N", BoolCleaner.Format.YESNO, "No"),
    ],
)
def test_boolean_clean_value_translations(input_val, out_fmt, expected_output):
    cleaner = BoolCleaner(out_format=out_fmt)
    assert cleaner.clean_value(input_val) == expected_output


def test_boolean_clean_value_returns_none_on_miss():
    cleaner = BoolCleaner()
    # Unrecognized or out-of-bounds string options safely fall through to None [cite: 1416]
    assert cleaner.clean_value("not_a_boolean_flag") is None
    assert cleaner.clean_value("pending") is None
