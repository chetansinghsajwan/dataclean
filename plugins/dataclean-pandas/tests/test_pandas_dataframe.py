"""Runs the shared DataFrame test suite against the pandas engine, plus pandas-specific checks."""

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests, FrameFactory


class TestPandasDataFrame(BaseDataFrameTests):
    """
    Invokes the entire reusable test suite specifically for Pandas.
    """

    @pytest.fixture
    def wrapper(self) -> PandasDataFrame:
        """Small two-row frame of raw messy data, the input most tests start from."""
        pd_df = pd.DataFrame(RAW_TEST_DATA)
        return PandasDataFrame(df=pd_df)

    @pytest.fixture
    def make_frame(self) -> FrameFactory:
        """Builds a frame from a dict, so shared tests can create their own data."""
        return lambda data: PandasDataFrame(df=pd.DataFrame(dict(data)))

    @pytest.fixture
    def numeric_wrapper(self) -> PandasDataFrame:
        """Five rows with distinct numbers and repeating categories, for sorting and grouping."""
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        pd_df = pd.DataFrame(data)
        return PandasDataFrame(df=pd_df)

    def test_count(self, wrapper: PandasDataFrame) -> None:
        """The fixture has two rows, so asking for the count should say 2. It is the
        simplest check that the wrapper really sees the data.
        """
        assert wrapper.count() == 2

    def test_count_empty(self) -> None:
        """A frame with no rows at all should count as 0 instead of blowing up. Empty
        inputs turn up in real pipelines more often than you would think.
        """
        pd_df = pd.DataFrame()
        wrapper = PandasDataFrame(df=pd_df)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: PandasDataFrame) -> None:
        """Collecting rows gives back plain tuples, one per row. That way nothing
        downstream has to know which engine produced them.
        """
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: PandasDataFrame) -> None:
        """We collect the numeric fixture and look at its first two rows. Values and
        column order should come out exactly as they went in.
        """
        result = numeric_wrapper.collect()
        assert result[0] == (1, 10, "A")
        assert result[1] == (2, 20, "B")

    def test_select_single_column(self, wrapper: PandasDataFrame) -> None:
        """Selecting one column by name should leave just that column. Cleaners often
        work on one field at a time, so this is the everyday case.
        """
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: PandasDataFrame) -> None:
        """Asking for two columns keeps those two and drops the rest, email in this
        case. It is how a cleaner narrows a wide table down to what it needs.
        """
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: PandasDataFrame) -> None:
        """Taking the first three rows should give three rows, in their original order.
        People use this to take a quick peek at a big table.
        """
        result = numeric_wrapper.limit(3)
        assert result.count() == 3
        collected = result.collect()
        assert collected[0] == (1, 10, "A")
        assert collected[2] == (3, 30, "A")

    def test_limit_zero(self, numeric_wrapper: PandasDataFrame) -> None:
        """Asking for zero rows is allowed and simply gives an empty result. Anyone
        computing a limit should not have to special-case zero.
        """
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: PandasDataFrame) -> None:
        """Sorting by value ascending should put 10 first and 50 last. It is the plain
        default, so it has to be right.
        """
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: PandasDataFrame) -> None:
        """Turning desc on flips the same list around, 50 down to 10. Handy when you
        want the biggest values first.
        """
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: PandasDataFrame) -> None:
        """We sort by category and then by value. Rows from the same category stay
        together and ties are broken by the second column, so the first two rows
        both belong to A.
        """
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        categories = [row[2] for row in collected]
        assert categories[0] == "A"
        assert categories[1] == "A"

    def test_strip_single_column(self, wrapper: PandasDataFrame) -> None:
        """Some names in the fixture have stray spaces around them. After stripping
        first_name, rahul and PRIYA should come out clean, because messy input is
        full of stray whitespace.
        """
        result = wrapper.strip("first_name")
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[1][0] == "PRIYA"

    def test_strip_multiple_columns(self, wrapper: PandasDataFrame) -> None:
        """Give strip a list of columns and each one gets trimmed, so both first and
        last names come out tidy.
        """
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][1] == "sharma"

    def test_strip_all_columns(self, wrapper: PandasDataFrame) -> None:
        """With no columns named, strip works on every text column. rahul and the email
        address both come back without padding.
        """
        result = wrapper.strip()
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][2] == "rahul+spam@gmail.com"

    def test_nullif_empty_strings(self) -> None:
        """In raw data a blank string really means missing. Calling nullif on col1
        turns its empty value into a real null and leaves the other values alone.
        """
        data = {"col1": ["a", "", "b"], "col2": ["x", "y", ""]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif("col1")
        collected = result.collect()
        assert collected[0][0] == "a"
        assert collected[1][0] is None
        assert collected[2][0] == "b"

    def test_nullif_multiple_columns(self) -> None:
        """Two columns each hold an empty string. After nullif on both, both blanks
        become real nulls.
        """
        data = {"col1": ["a", "", "b"], "col2": ["x", "", "z"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert collected[1][0] is None
        assert collected[1][1] is None

    def test_nullif_all_columns(self) -> None:
        """With no columns named, nullif looks at every column, so the blanks in col1
        and col2 both turn into nulls.
        """
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.nullif()
        collected = result.collect()
        assert collected[0][1] is None
        assert collected[1][0] is None

    def test_distinct_all_columns(self) -> None:
        """Two of the three rows are identical in every column. Distinct keeps just one
        of them, so three rows become two.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self) -> None:
        """Col2 differs from row to row, but we only ask about col1. Judged on col1
        alone the first two rows are twins, so we end up with two rows.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_filter_null_all_columns(self) -> None:
        """One row has a null in col1. With no columns named, a null anywhere removes
        the row, which leaves two.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self) -> None:
        """The null sits in col2 and we ask about col2 only, so that row is dropped and
        two remain. Nulls in columns we did not name would be ignored.
        """
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self) -> None:
        """One row has a null in col1 and another has one in col2. Naming both columns
        drops both rows and leaves a single clean one.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        pd_df = pd.DataFrame(data)
        wrapper = PandasDataFrame(df=pd_df)
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: PandasDataFrame) -> None:
        """Grouping by category should give back at least one group. It is a basic
        does-it-run-and-return-something check.
        """
        result = numeric_wrapper.group_by(["category"])
        assert result.count() > 0

    def test_agg_with_callable(self, numeric_wrapper: PandasDataFrame) -> None:
        """We pass our own function for the value column, a sum here, and the
        aggregation should return a result. That is how a cleaner asks for a custom
        summary.
        """
        agg_config = {"value": lambda x: x.sum()}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0


def test_bool_and_int_outputs_keep_nulls() -> None:
    """Casting a column that has a missing value to bool or int must keep it missing,
    not turn it into False or 0. A missing answer is not the same as a no.
    """
    from dataclean import DataType

    wrapper = PandasDataFrame(df=pd.DataFrame({"a": [True, None], "b": [2, None]}))
    wrapper.cast_cols({"a": DataType.BOOL, "b": DataType.INT})

    assert wrapper.df["a"].tolist()[0] is True
    assert wrapper.df["a"].isna().tolist() == [False, True]
    assert wrapper.df["b"].isna().tolist() == [False, True]
    assert dict(wrapper.cols()) == {"a": DataType.BOOL, "b": DataType.INT}


def test_copy_cols_keeps_values_and_types_exactly() -> None:
    """Copying a column should give an identical twin with the same values, missing
    entries and type. A copy that quietly changed the data would be worse than no
    copy.
    """
    from dataclean import DataType

    wrapper = PandasDataFrame(
        df=pd.DataFrame({"n": pd.array([1, None], dtype="Int64"), "s": ["a", None]})
    )
    wrapper.copy_cols({"n": "n_copy", "s": "s_copy"})

    assert wrapper.df["n_copy"].tolist() == [1, pd.NA]
    assert str(wrapper.df["n_copy"].dtype) == "Int64"
    assert wrapper.df["s_copy"].tolist() == ["a", None]
    assert dict(wrapper.cols())["n_copy"] == DataType.INT


def test_copy_cols_is_independent_of_the_source() -> None:
    """After copying column a we overwrite the original. The copy must still hold the
    old values, because a copy that follows its source is no copy at all.
    """
    wrapper = PandasDataFrame(df=pd.DataFrame({"a": ["x", "y"]}))
    wrapper.copy_cols({"a": "a_copy"})
    wrapper.df["a"] = ["changed", "changed"]

    assert wrapper.df["a_copy"].tolist() == ["x", "y"]
