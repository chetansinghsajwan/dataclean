import pandas as pd
from dataclean_pandas import PandasDataFrame

import dataclean


def test_clean():
    dataclean.config.dataframe_apis.append(PandasDataFrame)
    dataclean.config.cleaners.append(dataclean.EmailCleaner())

    uncleaned_df = pd.read_csv("tests/fixtures/uncleaned.csv")
    dataclean.clean(uncleaned_df)


def test_clean_column_cleaners_override_detection_by_name():
    df = pd.DataFrame({"contact": [" Bob@Example.COM "]})

    cleaned = dataclean.clean(
        PandasDataFrame(df), column_cleaners={"contact": "EmailCleaner"}
    )

    assert cleaned.df["contact"].iloc[0] == "bob@example.com"


def test_clean_ignore_cols_leave_a_column_uncleaned():
    df = pd.DataFrame({"email": [" Bob@Example.COM "]})

    cleaned = dataclean.clean(PandasDataFrame(df), ignore_cols=["email"])

    assert cleaned.df["email"].iloc[0] == " Bob@Example.COM "
