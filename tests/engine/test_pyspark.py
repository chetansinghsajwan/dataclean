from collections.abc import Generator

import pandas as pd
import pytest
from dataframe import RAW_TEST_DATA, BaseDataFrameTests
from pyspark.sql import SparkSession

from dataclean.engine.pyspark import PySparkDataFrame


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
