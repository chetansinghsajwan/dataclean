from collections.abc import Generator

import pandas as pd
import pytest
from dataclean_pyspark.dataframe import PySparkDataFrame
from pyspark.sql import SparkSession

from dataclean.testing.engine_contracts import RAW_TEST_DATA, BaseDataFrameTests


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


class TestPySparkDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for PySpark.
    """

    @pytest.fixture(autouse=True)
    def wrapper(self, spark: SparkSession) -> PySparkDataFrame:
        sp_df = spark.createDataFrame(pd.DataFrame(RAW_TEST_DATA))
        return PySparkDataFrame(df=sp_df)
