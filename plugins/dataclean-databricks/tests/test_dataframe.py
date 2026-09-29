from collections.abc import Generator

import pandas as pd
import pyspark.sql.types as spt
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


class TestDatabricksDataFrameNewMethods:
    """Test suite for new dataframe methods in Databricks."""

    @pytest.fixture
    def wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        sp_df = spark.createDataFrame(pd.DataFrame(RAW_TEST_DATA))
        return PysparkDataFrame(df=sp_df)

    @pytest.fixture
    def numeric_wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        return PysparkDataFrame(df=sp_df)

    def test_count(self, wrapper: PysparkDataFrame) -> None:
        assert wrapper.count() == 2

    def test_count_empty(self, spark: SparkSession) -> None:
        # An explicit schema is required since PySpark cannot infer a schema
        # from a pandas DataFrame that has no columns.
        schema = spt.StructType([spt.StructField("col1", spt.StringType(), True)])
        sp_df = spark.createDataFrame(
            pd.DataFrame(columns=pd.Index(["col1"])), schema=schema
        )
        wrapper = PysparkDataFrame(df=sp_df)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.collect()
        assert len(result) == 5
        # Verify first row has expected structure
        assert len(result[0]) == 3

    def test_select_single_column(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.limit(3)
        assert result.count() == 3

    def test_limit_zero(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        # Collect values from the second position (value column)
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        assert len(collected) == 5

    def test_distinct_all_columns(self, spark: SparkSession) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self, spark: SparkSession) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_strip_single_column(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.strip("first_name")
        collected = result.collect()
        # First element should be stripped
        assert collected[0][0].strip() == collected[0][0]
        assert collected[1][0].strip() == collected[1][0]

    def test_strip_multiple_columns(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert len(collected) == 2

    def test_strip_all_columns(self, wrapper: PysparkDataFrame) -> None:
        result = wrapper.strip()
        collected = result.collect()
        assert len(collected) == 2

    def test_nullif_empty_strings(self, spark: SparkSession) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "y", ""]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif("col1")
        collected = result.collect()
        assert len(collected) == 3

    def test_nullif_multiple_columns(self, spark: SparkSession) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "", "z"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert len(collected) == 3

    def test_nullif_all_columns(self, spark: SparkSession) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif()
        collected = result.collect()
        assert len(collected) == 3

    def test_filter_null_all_columns(self, spark: SparkSession) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self, spark: SparkSession) -> None:
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self, spark: SparkSession) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: PysparkDataFrame) -> None:
        result = numeric_wrapper.group_by(["category"])
        assert result.count() > 0

    def test_agg_with_callable(self, numeric_wrapper: PysparkDataFrame) -> None:
        import pyspark.sql.functions as F

        agg_config = {"value": F.sum("value")}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0
