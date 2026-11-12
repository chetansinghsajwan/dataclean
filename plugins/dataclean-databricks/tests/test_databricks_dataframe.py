"""Runs the shared DataFrame test suite against the Databricks (PySpark) engine."""

import os
from collections.abc import Generator

import pandas as pd
import pyspark.sql.types as spt
import pytest
from dataclean_databricks import PysparkDataFrame
from dataclean_databricks.catalog import new_session
from pyspark.sql import SparkSession

from dataclean import DataType
from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests, FrameFactory


@pytest.fixture(scope="session")
def spark() -> Generator[SparkSession, None, None]:
    """Opens one Spark session, skipping when no workspace credentials are set so tests do not hang."""
    # Without credentials, opening a session hangs instead of failing.
    if not (os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN")):
        pytest.skip("needs a Databricks workspace (DATABRICKS_HOST, DATABRICKS_TOKEN)")

    session = new_session()

    yield session  # ty: ignore[invalid-yield]
    session.stop()


class TestDatabricksDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Databricks.
    """

    @pytest.fixture(autouse=True)
    def wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        """Small two-row frame of raw messy data, the input most tests start from."""
        sp_df = spark.createDataFrame(pd.DataFrame(RAW_TEST_DATA))
        return PysparkDataFrame(df=sp_df)

    @pytest.fixture
    def make_frame(self, spark: SparkSession) -> FrameFactory:
        """Builds a frame from a dict, so shared tests can create their own data."""
        return lambda data: PysparkDataFrame(
            df=spark.createDataFrame(pd.DataFrame(dict(data)))
        )


class TestDatabricksDataFrameNewMethods:
    """Test suite for new dataframe methods in Databricks."""

    @pytest.fixture
    def wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        """Small two-row frame of raw messy data, the input most tests start from."""
        sp_df = spark.createDataFrame(pd.DataFrame(RAW_TEST_DATA))
        return PysparkDataFrame(df=sp_df)

    @pytest.fixture
    def numeric_wrapper(self, spark: SparkSession) -> PysparkDataFrame:
        """Five rows with distinct numbers and repeating categories, for sorting and grouping."""
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        return PysparkDataFrame(df=sp_df)

    def test_count(self, wrapper: PysparkDataFrame) -> None:
        """The fixture has two rows, so asking for the count should say 2. It is the
        simplest check that the wrapper really sees the data.
        """
        assert wrapper.count() == 2

    def test_count_empty(self, spark: SparkSession) -> None:
        """Same empty-frame case, but Spark cannot guess columns from nothing, so we
        give it a one-column schema. The count should still be 0.
        """
        # An explicit schema is required since PySpark cannot infer a schema
        # from a pandas DataFrame that has no columns.
        schema = spt.StructType([spt.StructField("col1", spt.StringType(), True)])
        sp_df = spark.createDataFrame(
            pd.DataFrame(columns=pd.Index(["col1"])), schema=schema
        )
        wrapper = PysparkDataFrame(df=sp_df)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: PysparkDataFrame) -> None:
        """Collecting rows gives back plain tuples, one per row. That way nothing
        downstream has to know which engine produced them.
        """
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: PysparkDataFrame) -> None:
        """We collect the five-row numeric fixture and check there are five rows with
        three values each. It is a quick shape check on what Spark hands back.
        """
        result = numeric_wrapper.collect()
        assert len(result) == 5
        # Verify first row has expected structure
        assert len(result[0]) == 3

    def test_select_single_column(self, wrapper: PysparkDataFrame) -> None:
        """Selecting one column by name should leave just that column. Cleaners often
        work on one field at a time, so this is the everyday case.
        """
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: PysparkDataFrame) -> None:
        """Asking for two columns keeps those two and drops the rest, email in this
        case. It is how a cleaner narrows a wide table down to what it needs.
        """
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Asking for three rows should give exactly three. It is the quick way to peek
        at a big table.
        """
        result = numeric_wrapper.limit(3)
        assert result.count() == 3

    def test_limit_zero(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Asking for zero rows is allowed and simply gives an empty result. Anyone
        computing a limit should not have to special-case zero.
        """
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Sorting by value ascending should put 10 first and 50 last. It is the plain
        default, so it has to be right.
        """
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        # Collect values from the second position (value column)
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Turning desc on flips the same list around, 50 down to 10. Handy when you
        want the biggest values first.
        """
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Sorting on two columns at once should still return all five rows. Nothing
        may go missing just because the sort key is a list.
        """
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        assert len(collected) == 5

    def test_distinct_all_columns(self, spark: SparkSession) -> None:
        """Two of the three rows are identical in every column. Distinct keeps just one
        of them, so three rows become two.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self, spark: SparkSession) -> None:
        """Col2 differs from row to row, but we only ask about col1. Judged on col1
        alone the first two rows are twins, so we end up with two rows.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_strip_single_column(self, wrapper: PysparkDataFrame) -> None:
        """Names in the fixture have stray spaces around them. After stripping
        first_name, the first two values should have no leading or trailing space.
        """
        result = wrapper.strip("first_name")
        collected = result.collect()
        # First element should be stripped
        assert collected[0][0].strip() == collected[0][0]
        assert collected[1][0].strip() == collected[1][0]

    def test_strip_multiple_columns(self, wrapper: PysparkDataFrame) -> None:
        """Stripping two columns at once should not lose any rows. Only the text
        changes, never the row count.
        """
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert len(collected) == 2

    def test_strip_all_columns(self, wrapper: PysparkDataFrame) -> None:
        """Calling strip with no columns is the do-it-everywhere form. It should still
        return both rows.
        """
        result = wrapper.strip()
        collected = result.collect()
        assert len(collected) == 2

    def test_nullif_empty_strings(self, spark: SparkSession) -> None:
        """Calling nullif on one column should not drop any rows, since it only blanks
        values out. Three rows go in and three come out.
        """
        data = {"col1": ["a", "", "b"], "col2": ["x", "y", ""]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif("col1")
        collected = result.collect()
        assert len(collected) == 3

    def test_nullif_multiple_columns(self, spark: SparkSession) -> None:
        """Two columns hold empty strings and we name both. All three rows should still
        be there afterwards.
        """
        data = {"col1": ["a", "", "b"], "col2": ["x", "", "z"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert len(collected) == 3

    def test_nullif_all_columns(self, spark: SparkSession) -> None:
        """With no columns named, nullif looks at everything. It still must not lose
        any of the three rows.
        """
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.nullif()
        collected = result.collect()
        assert len(collected) == 3

    def test_filter_null_all_columns(self, spark: SparkSession) -> None:
        """One row has a null in col1. With no columns named, a null anywhere removes
        the row, which leaves two.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self, spark: SparkSession) -> None:
        """The null sits in col2 and we ask about col2 only, so that row is dropped and
        two remain. Nulls in columns we did not name would be ignored.
        """
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self, spark: SparkSession) -> None:
        """One row has a null in col1 and another has one in col2. Naming both columns
        drops both rows and leaves a single clean one.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        sp_df = spark.createDataFrame(pd.DataFrame(data))
        wrapper = PysparkDataFrame(df=sp_df)
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: PysparkDataFrame) -> None:
        """Grouping by category should give back at least one group. It is a basic
        does-it-run-and-return-something check.
        """
        result = numeric_wrapper.group_by(["category"])
        assert result.count() > 0

    def test_agg_with_callable(self, numeric_wrapper: PysparkDataFrame) -> None:
        """We pass a Spark column function for the value column and the aggregation
        should return a result. That is how a cleaner asks for a custom summary.
        """
        import pyspark.sql.functions as F

        agg_config = {"value": F.sum("value")}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0


@pytest.mark.parametrize(
    "spark_type, expected",
    [
        (spt.StringType(), DataType.STR),
        (spt.BooleanType(), DataType.BOOL),
        (spt.ByteType(), DataType.INT),
        (spt.ShortType(), DataType.INT),
        (spt.IntegerType(), DataType.INT),
        (spt.LongType(), DataType.LONG),
        (spt.FloatType(), DataType.FLOAT),
        (spt.DoubleType(), DataType.DOUBLE),
        (spt.DateType(), DataType.DATE),
        (spt.TimestampType(), DataType.DATETIME),
        (spt.TimestampNTZType(), DataType.DATETIME),
        (spt.BinaryType(), DataType.STR),
    ],
)
def test_spark_types_map_to_engine_agnostic_types(
    spark_type: spt.DataType, expected: DataType
) -> None:
    """Each Spark type is translated into our own neutral data type. That way cleaners
    never have to know they are talking to Spark.
    """
    assert PysparkDataFrame._from_pyspark_data_type(spark_type) == expected
