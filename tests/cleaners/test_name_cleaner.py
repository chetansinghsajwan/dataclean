from unittest.mock import MagicMock

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import DataFrame, DataType, NameCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver

# ==============================================================================
# 1. METADATA & AUTO-DETECTION
# ==============================================================================


def test_name_cleaner_metadata() -> None:
    cleaner = NameCleaner()
    assert cleaner.name == "NameCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


@pytest.mark.parametrize(
    "col_name",
    [
        "fname",
        "lname",
        "mname",
        "FName",
        "lnamefname",
        "first_name",
        "FirstName",
        "last_name",
        "middle_name",
        "surname",
        "forename",
        "full_name",
        "given_name",
        "family_name",
        "client_fname",
    ],
)
def test_name_cleaner_matches_person_name_columns(col_name: str) -> None:
    mock_df = MagicMock(spec=DataFrame)
    assert NameCleaner().match_score(mock_df, (col_name,)) == 1.0


@pytest.mark.parametrize(
    "col_name",
    ["name", "username", "filename", "col_name", "colname", "hostname", "email"],
)
def test_name_cleaner_ignores_non_person_name_columns(col_name: str) -> None:
    mock_df = MagicMock(spec=DataFrame)
    assert NameCleaner().match_score(mock_df, (col_name,)) == 0.0


def test_name_cleaner_ignores_non_string_columns() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"first_name": [1, 2]}))
    assert NameCleaner().match_score(df, ("first_name",)) == 0.0


def test_name_cleaner_empty_cols_scores_zero() -> None:
    assert NameCleaner().match_score(MagicMock(spec=DataFrame), ()) == 0.0


# ==============================================================================
# 2. CLEANING (pass-through)
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "JOHN",
        "john smith",
        "McDonald",
        "HBOS",
        "R.P.",
        "GM & JW",
        "O'Neil",
        "123",
    ],
)
def test_name_cleaner_returns_values_unchanged(raw: str) -> None:
    assert NameCleaner().clean_row(raw) == raw


# ==============================================================================
# 3. AUTO-DETECTION END TO END
# ==============================================================================


def test_name_cleaner_is_assigned_by_the_resolver() -> None:
    cols = {"fname", "lname", "mname", "company", "dateofbirth"}
    df = PandasDataFrame(df=pd.DataFrame({c: ["x"] for c in cols}))

    assignments = Resolver(cleaners=(NameCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {"fname", "lname", "mname"}


def test_name_cleaner_in_the_pipeline_gets_input_normalization_and_placeholders_nulled() -> (
    None
):
    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "fname": ["JOHN", "  mary ", "", None],
                "lname": ["HBOS", "R.P.", "McDonald", "n/a"],
            }
        )
    )

    cleaned = Pipeline(cleaners=(NameCleaner(),)).fit_transform(df)

    result = cleaned.df
    assert result is not None
    fname = result["fname"].tolist()
    lname = result["lname"].tolist()

    # Case is untouched; whitespace is stripped, blanks and placeholders become null.
    assert fname[:2] == ["JOHN", "mary"]
    assert pd.isna(fname[2]) and pd.isna(fname[3])
    assert lname[:3] == ["HBOS", "R.P.", "McDonald"]
    assert pd.isna(lname[3])


@pytest.mark.parametrize("raw", ["N/A", "null", "-", "None", "undefined"])
def test_name_cleaner_nulls_placeholders(raw: str) -> None:
    assert NameCleaner().clean_row(raw) is None


@pytest.mark.parametrize("raw", ["Na", "Nan", "Null Singh"])
def test_name_cleaner_keeps_names_that_look_like_placeholders(raw: str) -> None:
    assert NameCleaner().clean_row(raw) == raw


def test_name_cleaner_null_tokens_can_be_set() -> None:
    assert NameCleaner(null_tokens=("unknown",)).clean_row("Unknown") is None
    assert NameCleaner(null_tokens=("unknown",)).clean_row("N/A") == "N/A"
