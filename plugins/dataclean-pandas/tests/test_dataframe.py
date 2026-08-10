import pandas as pd
import pytest
from dataclean_pandas.dataframe import PandasDataFrame

from dataclean.testing.engine_contracts import RAW_TEST_DATA, BaseDataFrameTests


class TestPandasDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Pandas.
    """

    @pytest.fixture(autouse=True)
    def wrapper(self) -> PandasDataFrame:
        pd_df = pd.DataFrame(RAW_TEST_DATA)
        return PandasDataFrame(df=pd_df)
