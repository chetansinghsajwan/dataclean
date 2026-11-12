"""Tests for DateTimeCleaner: parsing, output formats, day order, timezones and column layout."""

from unittest.mock import MagicMock
from zoneinfo import ZoneInfoNotFoundError

import pytest

from dataclean import DataFrame, DataType, DateTimeCleaner

# ==============================================================================
# 1. METADATA & PROPERTY HEURISTICS
# ==============================================================================


def test_datetime_cleaner_metadata():
    """The date cleaner should call itself DateTimeCleaner and produce one string
    column. The rest of the pipeline relies on both."""

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
    """Names like created_at, timestamp and transaction_date clearly mean dates, so
    they score full. Words that only contain letters like at or time, such as seat
    and format, must not be fooled into scoring."""
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
    """Dates arrive in many shapes, such as ISO, Indian day-first and 12-hour times.
    Each case feeds one of them in and checks it comes out in the output format we
    asked for."""
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
    """A bare time like 22:45 has no date in it. If you ask for a date out of it we
    return null, instead of making up a day."""
    cleaner = DateTimeCleaner(out_format=out_fmt)
    assert cleaner.clean_row(input_val) is None


def test_datetime_clean_value_returns_none_on_bad_string():
    """Text that is not a date, or a date that cannot exist, should not crash a long
    run. It just becomes null."""
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
    """When no output format is chosen, the result should look like what came in. A
    date stays a date, something with a time stays a datetime, and a time stays a
    time, whatever style it was written in."""
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
    """Some values can never be valid, like 31 February, a 25th hour or 13 PM. Words
    like yesterday and ambiguous two-digit years are not guessed at either, and
    all of them become null."""
    assert DateTimeCleaner().clean_row(input_val) is None


def test_datetime_day_first_controls_numeric_order():
    """A date like 03/04/1985 can be read two ways. By default we read it day first,
    which is how it is written in India, and day_first=False flips it, while year-
    first dates are never affected."""
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
    """Systems often fill missing dates with fake ones like 0001-01-01 or 9999-12-31.
    We null them by default, with or without a time, and you can keep them by
    turning the option off."""
    assert DateTimeCleaner().clean_row(input_val) is None
    assert DateTimeCleaner().clean_row(input_val + " 00:00:00") is None
    kept = DateTimeCleaner(null_placeholder_dates=False)
    assert kept.clean_row(input_val) == input_val


def test_datetime_strips_html_before_parsing():
    """Dates copied from web pages can have tags around them. We take the markup off
    first so the date still parses, and a value that is only markup becomes null."""
    cleaner = DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_DATE)
    assert cleaner.clean_row("<b>2003-04-08</b>") == "2003-04-08"
    assert cleaner.clean_row("<p>8 April\n 2003</p>") == "2003-04-08"
    assert cleaner.clean_row("<script>x()</script>") is None
    assert cleaner.clean_row("<br>") is None


def test_datetime_min_and_max_date():
    """You can set a window of dates that make sense, such as no one born before
    1920. Anything outside the window becomes null, while the edge dates
    themselves are allowed."""
    from datetime import date

    cleaner = DateTimeCleaner(min_date=date(1920, 1, 1), max_date=date(2030, 1, 1))
    assert cleaner.clean_row("1919-12-31") is None
    assert cleaner.clean_row("1920-01-01") == "1920-01-01"
    assert cleaner.clean_row("2030-01-02") is None


def test_datetime_converts_offsets_to_the_default_timezone():
    """If a value says what time zone it is in, we convert it into our default one so
    a column is consistent. Values without a zone are assumed to already be in it,
    and the date moves if the conversion crosses midnight."""
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
    """A time with a zone offset but no date cannot be converted safely, since
    offsets change through the year. So we return null rather than guess."""
    assert DateTimeCleaner().clean_row("22:45+05:30") is None


def test_datetime_unknown_timezone_name_is_rejected():
    """A mistyped time zone name should fail when the cleaner is created. That is
    much better than quietly using the wrong zone for every row."""
    with pytest.raises(ZoneInfoNotFoundError):
        DateTimeCleaner(default_timezone="Mars/Olympus")


# ==============================================================================
# 4. ALREADY-TYPED TEMPORAL COLUMNS ARE LEFT ALONE
# ==============================================================================


def test_datetime_cleaner_skips_columns_that_are_already_temporal():
    """If a column is already a real date type there is nothing to clean. It scores
    zero, while a column of date text still scores full."""
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
    """Running the whole pipeline should not break columns that are already dates.
    The real date column keeps its type, and only the text date column is cleaned
    into a standard string."""
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
    """A column should look uniform when it is done, so one layout is chosen for
    every row based on the whole column. When dates and bare times are mixed, the
    column name decides which one wins."""
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    from dataclean.pipeline import Pipeline

    cleaned = Pipeline(
        column_cleaners={col: DateTimeCleaner()}, auto_detect=False
    ).fit_transform(PandasDataFrame(df=pd.DataFrame({col: raw})))

    assert cleaned.df is not None
    assert [None if v != v else v for v in cleaned.df[col].tolist()] == expected


def test_datetime_removes_emoji_before_parsing():
    """People sometimes add a calendar emoji next to a date. We drop it so the date
    still parses, and a value that is only an emoji becomes null."""
    cleaner = DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_DATE)
    assert cleaner.clean_row("2003-04-08 \U0001f4c5") == "2003-04-08"
    assert cleaner.clean_row("\U0001f4c5") is None
