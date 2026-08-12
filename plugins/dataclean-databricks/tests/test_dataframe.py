from collections.abc import Generator

import pandas as pd
import pytest
from databricks.connect import DatabricksEnv, DatabricksSession
from dataclean_databricks import PysparkDataFrame
from pyspark.sql import SparkSession

from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests


@pytest.fixture(scope="session")
def spark() -> Generator[SparkSession, None, None]:
    spark_env = DatabricksEnv().withAutoDependencies(upload_local=True)
    session = DatabricksSession.builder.withEnvironment(spark_env).getOrCreate()

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
