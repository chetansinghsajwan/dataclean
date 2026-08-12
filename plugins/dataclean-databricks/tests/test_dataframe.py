from collections.abc import Generator

import pandas as pd
import pytest
from dataclean_databricks import PysparkDataFrame
from pyspark.sql import SparkSession

from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests


@pytest.fixture(scope="session")
def spark() -> Generator[SparkSession, None, None]:
    session = (
        SparkSession.builder.master("local[2]")
        .appName("WrapperTesting")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )

    yield session
    session.stop()


class TestDatabricksDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Databricks.
    """

    @pytest.fixture(autouse=True)
    def wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        sp_df = spark.createDataFrame(pd.DataFrame(RAW_TEST_DATA))
        return PysparkDataFrame(df=sp_df)
