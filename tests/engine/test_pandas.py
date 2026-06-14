from typing import Any

import pandas as pd
import pytest
from dataframe import RAW_TEST_DATA, BaseDataFrameTests

from dataclean.engine.pandas import PandasDataFrame


class TestPandasDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Pandas.
    """

    @pytest.fixture(autouse=True)
    def wrapper(self) -> Any:
        pd_df = pd.DataFrame(RAW_TEST_DATA)
        return PandasDataFrame(df=pd_df)
        pass
