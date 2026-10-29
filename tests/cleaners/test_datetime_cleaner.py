from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame, DataType, DateTimeCleaner

# ==============================================================================
# 1. METADATA & PROPERTY HEURISTICS
# ==============================================================================


def test_datetime_cleaner_metadata():

    cleaner = DateTimeCleaner()
    assert cleaner.name == "DateTimeCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


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
    mock_df = MagicMock(spec=DataFrame)
    assert cleaner.match_score(mock_df, (col_name,)) == expected_confidence


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
    assert cleaner.clean_row(input_val) == expected_output


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
    assert cleaner.clean_row(input_val) is None


def test_datetime_clean_value_returns_none_on_bad_string():
    cleaner = DateTimeCleaner()
    # Unparseable temporal string tokens fall out safely as None
    assert cleaner.clean_row("not-a-date") is None
    assert cleaner.clean_row("2026/13/45") is None


# ==============================================================================
# 4. ALREADY-TYPED TEMPORAL COLUMNS ARE LEFT ALONE
# ==============================================================================


def test_datetime_cleaner_skips_columns_that_are_already_temporal():
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "created_at": pd.to_datetime(["2024-01-02 03:04:05"]),
                "date_text": ["2024-01-02"],
            }
        )
    )
    cleaner = DateTimeCleaner()

    assert dict(df.cols())["created_at"] == DataType.DATETIME
    assert cleaner.match_score(df, ("created_at",)) == 0.0
    assert cleaner.match_score(df, ("date_text",)) == 1.0


def test_pipeline_does_not_turn_temporal_columns_into_strings():
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    from dataclean.pipeline import Pipeline

    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "created_at": pd.to_datetime(["2024-01-02 03:04:05"]),
                "date_text": ["02/01/2024"],
            }
        )
    )

    cleaned = Pipeline(cleaners=(DateTimeCleaner(),)).fit_transform(df)

    types = dict(cleaned.cols())
    assert types["created_at"] == DataType.DATETIME
    assert types["date_text"] == DataType.STR
    result = cleaned.df
    assert result is not None
    assert result["date_text"].tolist() == ["2024-01-02T00:00:00"]
