import pandas as pd

from dataclean import dataclean
from dataclean.cleaners.email_cleaner import EmailCleaner
from dataclean.engine.pandas import PandasDataFrame


def test_clean():
    dataclean.config.dataframe_apis.append(PandasDataFrame)
    dataclean.config.cleaners.append(EmailCleaner())

    uncleaned_df = pd.read_csv("tests/fixtures/uncleaned.csv")
    cleaned_df = dataclean.clean(uncleaned_df)

    cleaned_df
