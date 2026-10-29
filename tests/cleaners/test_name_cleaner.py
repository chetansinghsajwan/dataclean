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
# 2. CLEANING
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("JOHN", "John"),
        ("john smith", "John Smith"),
        ("  mary   ann  ", "Mary Ann"),
        ("o'neil", "O'Neil"),
        ("D’ANGELO", "D’Angelo"),
        ("smith-jones", "Smith-Jones"),
        ("mcdonald", "McDonald"),
        ("MCDONALD", "McDonald"),
        ("mc", "Mc"),
        ("VAN DER BERG", "Van der Berg"),
        ("ludwig van beethoven", "Ludwig van Beethoven"),
        ("john smith jr.", "John Smith Jr."),
        ("JOHN SMITH III", "John Smith III"),
        ("j. k. rowling", "J. K. Rowling"),
        ("é lise", "É Lise"),
    ],
)
def test_name_cleaner_recases_single_case_names(raw: str, expected: str) -> None:
    assert NameCleaner().clean_row(raw) == expected


@pytest.mark.parametrize("raw", ["McDonald", "John smith", "van der Berg", "O'Neil"])
def test_name_cleaner_preserves_mixed_case_by_default(raw: str) -> None:
    assert NameCleaner().clean_row(raw) == raw


def test_name_cleaner_mixed_case_is_only_whitespace_normalized() -> None:
    assert NameCleaner().clean_row("McDonald   Smith") == "McDonald Smith"


def test_name_cleaner_can_recase_mixed_case() -> None:
    cleaner = NameCleaner(preserve_mixed_case=False)
    assert cleaner.clean_row("jOHN") == "John"
    assert cleaner.clean_row("mcDONALD") == "McDonald"


@pytest.mark.parametrize(
    "raw", ["n/a", "N/A", "unknown", "NULL", "-", "?", "123", "..."]
)
def test_name_cleaner_placeholders_and_letterless_values_become_none(raw: str) -> None:
    assert NameCleaner().clean_row(raw) is None


def test_name_cleaner_extra_null_values() -> None:
    cleaner = NameCleaner(extra_null_values=("Deceased",))
    assert cleaner.clean_row("deceased") is None
    assert cleaner.clean_row("jane") == "Jane"


def test_name_cleaner_is_idempotent() -> None:
    cleaner = NameCleaner()
    once = cleaner.clean_row("VAN DER BERG o'neil-smith jr.")
    assert once is not None
    assert cleaner.clean_row(once) == once


# ==============================================================================
# 3. AUTO-DETECTION END TO END
# ==============================================================================


def test_name_cleaner_is_assigned_by_the_resolver() -> None:
    cols = {"fname", "lname", "mname", "company", "dateofbirth"}
    df = PandasDataFrame(df=pd.DataFrame({c: ["x"] for c in cols}))

    assignments = Resolver(cleaners=(NameCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {"fname", "lname", "mname"}


def test_name_cleaner_in_the_pipeline() -> None:
    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "fname": ["JOHN", "  mary ", "", None],
                "lname": ["MCDONALD", "van der berg", "n/a", "O'Neil"],
            }
        )
    )

    cleaned = Pipeline(cleaners=(NameCleaner(),)).fit_transform(df)

    result = cleaned.df
    assert result is not None
    fname = result["fname"].tolist()
    lname = result["lname"].tolist()

    assert fname[:2] == ["John", "Mary"]
    assert pd.isna(fname[2])
    assert lname[0] == "McDonald"
    assert lname[1] == "Van der Berg"
    assert pd.isna(lname[2])
    assert lname[3] == "O'Neil"
