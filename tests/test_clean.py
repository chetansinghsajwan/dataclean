import pandas as pd
from dataclean_pandas import PandasDataFrame

import dataclean
from dataclean.cleaners.email_cleaner import EmailCleaner


def test_clean():
    dataclean.config.dataframe_apis.append(PandasDataFrame)
    dataclean.config.cleaners.append(EmailCleaner())

    uncleaned_df = pd.read_csv("tests/fixtures/uncleaned.csv")
    dataclean.clean(uncleaned_df)
