import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests


class TestPandasDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Pandas.
    """

    @pytest.fixture
    def wrapper(self) -> PandasDataFrame:
        pd_df = pd.DataFrame(RAW_TEST_DATA)
        return PandasDataFrame(df=pd_df)

    @pytest.fixture
    def numeric_wrapper(self) -> PandasDataFrame:
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        pd_df = pd.DataFrame(data)
        return PandasDataFrame(df=pd_df)

    def test_count(self, wrapper: PandasDataFrame) -> None:
        assert wrapper.count() == 2

    def test_count_empty(self) -> None:
        pd_df = pd.DataFrame()
        wrapper = PandasDataFrame(df=pd_df)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.collect()
        assert result[0] == (1, 10, "A")
        assert result[1] == (2, 20, "B")

    def test_select_single_column(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.limit(3)
        assert result.count() == 3
        collected = result.collect()
        assert collected[0] == (1, 10, "A")
        assert collected[2] == (3, 30, "A")

    def test_limit_zero(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        categories = [row[2] for row in collected]
        assert categories[0] == "A"
        assert categories[1] == "A"

    def test_strip_single_column(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.strip("first_name")
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[1][0] == "PRIYA"

    def test_strip_multiple_columns(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][1] == "sharma"

    def test_strip_all_columns(self, wrapper: PandasDataFrame) -> None:
        result = wrapper.strip()
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][2] == "rahul+spam@gmail.com"

    def test_nullif_empty_strings(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "y", ""]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif("col1")
        collected = result.collect()
        assert collected[0][0] == "a"
        assert collected[1][0] is None
        assert collected[2][0] == "b"

    def test_nullif_multiple_columns(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "", "z"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert collected[1][0] is None
        assert collected[1][1] is None

    def test_nullif_all_columns(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif()
        collected = result.collect()
        assert collected[0][1] is None
        assert collected[1][0] is None

    def test_distinct_all_columns(self) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_filter_null_all_columns(self) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self) -> None:
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: PandasDataFrame) -> None:
        result = numeric_wrapper.group_by(["category"])
        assert result.count() > 0

    def test_agg_with_callable(self, numeric_wrapper: PandasDataFrame) -> None:
        agg_config = {"value": lambda x: x.sum()}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0
