"""Tests for the top-level dataclean.clean entry point."""

import pandas as pd
from dataclean_pandas import PandasDataFrame

import dataclean


def test_clean():
    """A quick smoke test using a real sample file. We register the pandas support and the email cleaner and just check that cleaning the whole table runs without errors."""
    dataclean.config.dataframe_apis.append(PandasDataFrame)
    dataclean.config.cleaners.append(dataclean.EmailCleaner())

    uncleaned_df = pd.read_csv("tests/fixtures/uncleaned.csv")
    dataclean.clean(uncleaned_df)


def test_clean_column_cleaners_override_detection_by_name():
    """The column is called contact, which tells us nothing about emails. Naming the email cleaner for it by hand gets the address lowercased and trimmed."""
    df = pd.DataFrame({"contact": [" Bob@Example.COM "]})

    cleaned = dataclean.clean(
        PandasDataFrame(df), column_cleaners={"contact": "EmailCleaner"}
    )

    assert cleaned.df["contact"].iloc[0] == "bob@example.com"


def test_clean_ignore_cols_leave_a_column_uncleaned():
    """An email column would normally be cleaned. When it is listed as ignored, the messy original value, spaces and capitals included, is kept."""
    df = pd.DataFrame({"email": [" Bob@Example.COM "]})

    cleaned = dataclean.clean(PandasDataFrame(df), ignore_cols=["email"])

    assert cleaned.df["email"].iloc[0] == " Bob@Example.COM "
