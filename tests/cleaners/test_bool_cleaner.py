"""Boolean cleaner tests: detection by name and value, mapping to output formats, unknown values and ID-column guards."""

import pytest

from dataclean import BoolCleaner, ColRenamer, DataType
from dataclean.utils.case import TextCase

_words = ColRenamer().words

# ==============================================================================
# 1. CORE METADATA & DATA TYPE HEURISTICS
# ==============================================================================


def test_boolean_cleaner_metadata():
    """The type of the output column depends on the format. True/false gives a real boolean and yes/no gives text."""
    cleaner = BoolCleaner(out_format=BoolCleaner.Format.TRUEFALSE)
    assert cleaner.name == "BoolCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.BOOL

    str_cleaner = BoolCleaner(out_format=BoolCleaner.Format.YESNO)
    assert len(str_cleaner.outputs.cols) == 1
    assert str_cleaner.outputs.cols[0].dtype == DataType.STR


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
def test_boolean_cleaner_confidence(
    col_name, expected_confidence, mock_df_with_value_counts
):
    """Only the column name varies here. Flag-style names score full marks and others score zero, and we pass an empty value sample to show the name alone decides."""
    cleaner = BoolCleaner()
    # Name-based matching (prefix/suffix) short-circuits before value-based
    # auto matching, so an empty collect() is fine for all cases here.
    mock_df = mock_df_with_value_counts([])
    assert (
        cleaner.match_score(mock_df, (col_name,), _words(col_name))
        == expected_confidence
    )


# ==============================================================================
# 1b. MATCH SCORE: VALUE-BASED AUTO MATCHING (inherited from EnumCleaner)
# ==============================================================================


def test_boolean_cleaner_auto_matches_by_value_when_name_does_not_match(
    mock_df_with_value_counts,
):
    """The column is called toggle, which matches no flag naming rule, but its values are all true or false. We still claim it, because oddly named flags are common."""
    # "toggle" hits neither the default prefixes/suffixes nor any match word
    cleaner = BoolCleaner()
    mock_df = mock_df_with_value_counts([("true", 7), ("false", 3)])
    assert (
        cleaner.match_score(mock_df, ("toggle",), _words("toggle"))
        == BoolCleaner.MAX_SCORE
    )


def test_boolean_cleaner_auto_matching_partial_ratio(mock_df_with_value_counts):
    """Eight of ten values are yes or no and two are maybe. The score is 0.8, the share that fit, so mostly-boolean columns rank high without being treated as perfect."""
    cleaner = BoolCleaner()
    mock_df = mock_df_with_value_counts(
        [("yes", 4), ("no", 4), ("maybe", 2)],
    )
    # 4 + 4 matched out of 10 total occurrences
    assert cleaner.match_score(mock_df, ("toggle",), _words("toggle")) == pytest.approx(
        0.8
    )


def test_boolean_cleaner_auto_matching_no_values_match(mock_df_with_value_counts):
    """A column of fruit names has nothing to do with booleans. It scores zero so we never claim it by mistake."""
    cleaner = BoolCleaner()
    mock_df = mock_df_with_value_counts([("apple", 1), ("banana", 1)])
    assert (
        cleaner.match_score(mock_df, ("toggle",), _words("toggle"))
        == BoolCleaner.MIN_SCORE
    )


def test_boolean_cleaner_auto_matching_case_insensitive(mock_df_with_value_counts):
    """Sources write YES, Yes and yes interchangeably. Detection should not care about case."""
    cleaner = BoolCleaner()
    mock_df = mock_df_with_value_counts([("YES", 1), ("NO", 1)])
    assert (
        cleaner.match_score(mock_df, ("toggle",), _words("toggle"))
        == BoolCleaner.MAX_SCORE
    )


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
    """Booleans are written in many ways, such as yes, 1, T and on. Each one is checked against every output style, from native booleans to digits to words."""
    cleaner = BoolCleaner(out_format=out_fmt)
    assert cleaner.clean_row(input_val) == expected_output


def test_boolean_clean_value_returns_none_on_miss():
    """A word like pending is neither true nor false. We return null rather than guess an answer."""
    cleaner = BoolCleaner()
    # Unrecognized or out-of-bounds string options safely fall through to None [cite: 1416]
    assert cleaner.clean_row("not_a_boolean_flag") is None
    assert cleaner.clean_row("pending") is None


# ==============================================================================
# 1c. MATCH SCORE: NUMERIC COLUMNS (IDs/codes must not be mistaken for flags)
# ==============================================================================


def _pandas_df(**cols):
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    return PandasDataFrame(df=pd.DataFrame(cols))


def test_boolean_cleaner_rejects_numeric_id_column_that_is_mostly_ones():
    """A column of mostly 1s with a few 2s and 3s looks flag-like at first glance. A real flag never holds 2 or 3, so this is an ID or code and is left alone."""
    # 1 is a recognized flag value, but 2 and 3 are not: a flag column never has them.
    df = _pandas_df(contacttypeid=[1, 1, 1, 1, 1, 1, 2, 2, 3, 1])
    assert (
        BoolCleaner().match_score(df, ("contacttypeid",), _words("contacttypeid"))
        == BoolCleaner.MIN_SCORE
    )


def test_boolean_cleaner_accepts_numeric_column_with_only_flag_values():
    """A number column that holds nothing but 0s and 1s is a true flag. It should be claimed with full score."""
    df = _pandas_df(externaluse=[0, 1, 1, 0, 1])
    assert (
        BoolCleaner().match_score(df, ("externaluse",), _words("externaluse"))
        == BoolCleaner.MAX_SCORE
    )


def test_boolean_cleaner_ignores_status_name_for_numeric_codes():
    """Names ending in status usually do suggest a flag, but this one holds codes from 0 to 3. The values override the name and the score is zero."""
    # "status" suffix would match by name, but these are multi-valued codes.
    df = _pandas_df(idvstatus=[0, 1, 2, 3, 1, 0])
    assert (
        BoolCleaner().match_score(df, ("idvstatus",), _words("idvstatus"))
        == BoolCleaner.MIN_SCORE
    )


def test_boolean_cleaner_name_match_still_works_for_string_columns():
    """For text columns the name is trusted. A column called is_active is claimed even if one value, like maybe, is not a clean boolean."""
    df = _pandas_df(is_active=["Y", "N", "maybe"])
    assert (
        BoolCleaner().match_score(df, ("is_active",), _words("is_active"))
        == BoolCleaner.MAX_SCORE
    )


def test_boolean_cleaner_boolean_typed_column_matches_regardless_of_name():
    """A column that is already stored as true and false is plainly a flag. The cleaner claims it whatever it is called."""
    df = _pandas_df(whatever=[True, False, True])
    assert (
        BoolCleaner().match_score(df, ("whatever",), _words("whatever"))
        == BoolCleaner.MAX_SCORE
    )


# ==============================================================================
# 9. EXTRA VARIANTS AND THE YN FORMAT
# ==============================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        ("on", True),
        ("ON", True),
        ("enabled", True),
        ("1.0", True),
        ("off", False),
        ("Disabled", False),
        ("0.0", False),
    ],
)
def test_boolean_cleaner_accepts_toggle_and_float_variants(value, expected):
    """Exports often write on and off, or floats like 1.0 and 0.0. These are read as true and false, and the checks use identity so we know we get real booleans back."""
    assert BoolCleaner().clean_row(value) is expected


@pytest.mark.parametrize("value", ["maybe", "unknown", "ok", "2"])
def test_boolean_cleaner_unrecognized_values_become_none(value):
    """Words like maybe and ok, and the number 2, are not clearly true or false. All of them become null."""
    assert BoolCleaner().clean_row(value) is None


def test_boolean_cleaner_yn_format():
    """In Y/N mode with upper case, true is written as Y and false as N. Both a word like yes and a digit like 0 are accepted as input."""
    cleaner = BoolCleaner(out_format=BoolCleaner.Format.YN, out_case=TextCase.UPPER)
    assert cleaner.true_out == "Y"
    assert cleaner.false_out == "N"
    assert cleaner.clean_row("yes") == "Y"
    assert cleaner.clean_row("0") == "N"


def test_bool_cleaner_ignores_an_id_column_of_ones() -> None:
    """The column contacttypeid_3 is all 1s, which could pass for a flag, but its name marks it as an ID even with the copy number. The real flag column next to it, optout, should still score above zero."""
    import pandas as pd
    from dataclean_pandas import PandasDataFrame

    from dataclean.engine import DataFrame  # noqa: F401

    df = PandasDataFrame(
        df=pd.DataFrame({"contacttypeid_3": ["1", "1", "1"], "optout": ["1", "0", "1"]})
    )

    assert (
        BoolCleaner().match_score(df, ("contacttypeid_3",), _words("contacttypeid_3"))
        == 0.0
    )
    assert BoolCleaner().match_score(df, ("optout",), _words("optout")) > 0.0


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\u2705", True),
        ("\u2714\ufe0f", True),
        ("\u2713", True),
        ("\u2611\ufe0f", True),
        ("\U0001f44d", True),
        ("\u274c", False),
        ("\u2716\ufe0f", False),
        ("\u2717", False),
        ("\u2612", False),
        ("\U0001f44e", False),
    ],
)
def test_bool_cleaner_reads_flag_emoji(raw: str, expected: bool) -> None:
    """People sometimes mark yes or no with tick and cross symbols. They are read as true and false."""
    assert BoolCleaner().clean_row(raw) is expected
