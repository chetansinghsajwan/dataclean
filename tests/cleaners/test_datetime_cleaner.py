from unittest.mock import MagicMock
from zoneinfo import ZoneInfoNotFoundError

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
        ("createdat", 1.0),
        ("updatedAt", 1.0),
        ("format", 0.0),
        ("seat", 0.0),
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
# 3. FORMATS, DAY ORDER, PLACEHOLDER DATES AND TIMEZONES
# ==============================================================================


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        # Date-only input stays a date; input with a time stays a datetime.
        ("1985-03-14", "1985-03-14"),
        ("1985-03-14 00:00:00", "1985-03-14T00:00:00"),
        ("19850314", "1985-03-14"),
        ("1985.03.14", "1985-03-14"),
        ("14 Mar 1985", "1985-03-14"),
        ("14 March 1985", "1985-03-14"),
        ("March 14, 1985", "1985-03-14"),
        ("14-Mar-1985", "1985-03-14"),
        ("15/01/2020 10:30", "2020-01-15T10:30:00"),
        ("2020-01-15 10:30 PM", "2020-01-15T22:30:00"),
        ("2020-01-15T10:30:00.5", "2020-01-15T10:30:00.500000"),
        ("22:45", "22:45:00"),
    ],
)
def test_datetime_auto_output_follows_the_input(input_val, expected_output):
    assert DateTimeCleaner().clean_row(input_val) == expected_output


@pytest.mark.parametrize(
    "input_val",
    [
        "31/02/1990",
        "2026/13/45",
        "yesterday",
        "14-03-85",
        "2020-01-15 25:00",
        "13:00 PM",
    ],
)
def test_datetime_rejects_impossible_and_unreadable_values(input_val):
    assert DateTimeCleaner().clean_row(input_val) is None


def test_datetime_day_first_controls_numeric_order():
    assert DateTimeCleaner().clean_row("03/04/1985") == "1985-04-03"
    assert DateTimeCleaner().clean_row("03/14/1985") is None
    month_first = DateTimeCleaner(day_first=False)
    assert month_first.clean_row("03/04/1985") == "1985-03-04"
    assert month_first.clean_row("03/14/1985") == "1985-03-14"
    assert month_first.clean_row("19/06/2026") is None
    # Year-first values do not depend on the flag.
    assert month_first.clean_row("2026-06-19") == "2026-06-19"


@pytest.mark.parametrize(
    "input_val", ["0001-01-01", "1900-01-01", "2099-12-31", "9999-12-31"]
)
def test_datetime_placeholder_dates_become_none_unless_disabled(input_val):
    assert DateTimeCleaner().clean_row(input_val) is None
    assert DateTimeCleaner().clean_row(input_val + " 00:00:00") is None
    kept = DateTimeCleaner(null_placeholder_dates=False)
    assert kept.clean_row(input_val) == input_val


def test_datetime_strips_html_before_parsing():
    cleaner = DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_DATE)
    assert cleaner.clean_row("<b>2003-04-08</b>") == "2003-04-08"
    assert cleaner.clean_row("<p>8 April\n 2003</p>") == "2003-04-08"
    assert cleaner.clean_row("<script>x()</script>") is None
    assert cleaner.clean_row("<br>") is None


def test_datetime_min_and_max_date():
    from datetime import date

    cleaner = DateTimeCleaner(min_date=date(1920, 1, 1), max_date=date(2030, 1, 1))
    assert cleaner.clean_row("1919-12-31") is None
    assert cleaner.clean_row("1920-01-01") == "1920-01-01"
    assert cleaner.clean_row("2030-01-02") is None


def test_datetime_converts_offsets_to_the_default_timezone():
    assert (
        DateTimeCleaner().clean_row("2020-01-15T10:30:00Z")
        == "2020-01-15T10:30:00+00:00"
    )
    assert (
        DateTimeCleaner().clean_row("2020-01-15T10:30:00+05:30")
        == "2020-01-15T05:00:00+00:00"
    )
    india = DateTimeCleaner(default_timezone="Asia/Kolkata")
    assert india.clean_row("2020-01-15T10:30:00Z") == "2020-01-15T16:00:00+05:30"
    # No offset: taken to be in the default timezone and left as written.
    assert india.clean_row("2020-01-15 10:30:00") == "2020-01-15T10:30:00"
    # The date changes when the conversion crosses midnight.
    assert india.clean_row("2020-01-15T20:00:00Z") == "2020-01-16T01:30:00+05:30"
    assert (
        DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_DATE).clean_row(
            "2020-01-15T20:00:00-05:00"
        )
        == "2020-01-16"
    )


def test_datetime_time_only_with_offset_is_rejected():
    assert DateTimeCleaner().clean_row("22:45+05:30") is None


def test_datetime_unknown_timezone_name_is_rejected():
    with pytest.raises(ZoneInfoNotFoundError):
        DateTimeCleaner(default_timezone="Mars/Olympus")


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
    assert result["date_text"].tolist() == ["2024-01-02"]


# ==============================================================================
# ONE LAYOUT PER COLUMN
# ==============================================================================


@pytest.mark.parametrize(
    "col, raw, expected",
    [
        (
            "d",
            ["2026-06-19", "19/06/2026 22:45", "22:45"],
            ["2026-06-19T00:00:00", "2026-06-19T22:45:00", "0001-01-01T22:45:00"],
        ),
        ("d", ["19 Jun 2026", "2026-06-20"], ["2026-06-19", "2026-06-20"]),
        ("d", ["10:00", "11:30 pm"], ["10:00:00", "23:30:00"]),
        # Midnight carries no time of day, so the column is dates.
        (
            "dob",
            ["1985-03-14", "1985-03-14 00:00:00", "14/03/1985"],
            ["1985-03-14"] * 3,
        ),
        # Dates mixed with bare times: the column name picks one.
        ("dob", ["1985-03-14", "10:00"], ["1985-03-14", None]),
        ("start_time", ["1985-03-14", "10:00"], ["00:00:00", "10:00:00"]),
    ],
)
def test_auto_format_writes_one_layout_for_the_whole_column(
    col: str, raw: list[str], expected: list[str | None]
) -> None:
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    from dataclean.pipeline import Pipeline

    cleaned = Pipeline(
        column_cleaners={col: DateTimeCleaner()}, auto_detect=False
    ).fit_transform(PandasDataFrame(df=pd.DataFrame({col: raw})))

    assert cleaned.df is not None
    assert [None if v != v else v for v in cleaned.df[col].tolist()] == expected
