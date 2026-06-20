from unittest.mock import MagicMock

import pytest

from dataclean.cleaners.datetime_cleaner import DateTimeCleaner

# ==============================================================================
# 1. METADATA & PROPERTY HEURISTICS
# ==============================================================================


def test_datetime_cleaner_metadata():
    cleaner = DateTimeCleaner()
    assert cleaner.name() == "DateTimeCleaner"
    assert cleaner.output_schema() == "str"


@pytest.mark.parametrize(
    "col_name, expected_confidence",
    [
        ("created_at", 1.0),
        ("updated_time", 1.0),
        ("transaction_date", 1.0),
        ("timestamp", 1.0),
        ("user_id", 0.0),
        ("first_name", 0.0),
    ],
)
def test_datetime_cleaner_confidence(col_name, expected_confidence):
    cleaner = DateTimeCleaner()
    mock_df = MagicMock()
    assert cleaner.get_data_type_confidence(mock_df, (col_name,)) == expected_confidence


# ==============================================================================
# 2. FUNCTIONAL MATCHING & TRANSFORMATION TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Standard Full Datetime Inputs ---
        (
            "2026-06-19 22:45:00",
            DateTimeCleaner.Format.ISO_DATETIME,
            "2026-06-19T22:45:00",
        ),
        ("2026-06-19T22:45:00", DateTimeCleaner.Format.ISO_DATE, "2026-06-19"),
        ("2026-06-19 22:45:00", DateTimeCleaner.Format.ISO_TIME, "22:45:00"),
        # --- Regional & Alternate Date Variations ---
        ("19-06-2026", DateTimeCleaner.Format.ISO_DATE, "2026-06-19"),
        ("19/06/2026", DateTimeCleaner.Format.INDIAN_DATE, "19-06-2026"),
        ("2026-06-19", DateTimeCleaner.Format.ISO_DATETIME, "2026-06-19T00:00:00"),
        # --- Pure Time Fields Handling ---
        ("22:45:00", DateTimeCleaner.Format.ISO_TIME, "22:45:00"),
        ("10:45 PM", DateTimeCleaner.Format.ISO_TIME, "22:45:00"),
    ],
)
def test_datetime_clean_value_success(input_val, out_fmt, expected_output):
    cleaner = DateTimeCleaner(out_format=out_fmt)
    assert cleaner.clean_value(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val, out_fmt",
    [
        # Requesting a date structure out of a pure time token should return None
        ("22:45:00", DateTimeCleaner.Format.ISO_DATE),
        ("10:45 PM", DateTimeCleaner.Format.INDIAN_DATE),
    ],
)
def test_datetime_clean_value_invalid_coercions(input_val, out_fmt):
    cleaner = DateTimeCleaner(out_format=out_fmt)
    assert cleaner.clean_value(input_val) is None


def test_datetime_clean_value_returns_none_on_bad_string():
    cleaner = DateTimeCleaner()
    # Unparseable temporal string tokens fall out safely as None
    assert cleaner.clean_value("not-a-date") is None
    assert cleaner.clean_value("2026/13/45") is None
