"""Runs the shared DataFrame test suite against the Ibis engine, plus Ibis-specific checks."""

import ibis
import pandas as pd
import pytest
from dataclean_ibis import IbisDataFrame

from dataclean.engine.dataframe import Aggregators, DataReader, DataType, DataWriter
from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests, FrameFactory


class TestIbisDataFrame(BaseDataFrameTests):
    """Invokes the entire reusable test suite specifically for Ibis."""

    @pytest.fixture
    def wrapper(self) -> IbisDataFrame:
        """Small two-row frame of raw messy data, the input most tests start from."""
        table = ibis.memtable(pd.DataFrame(RAW_TEST_DATA))
        return IbisDataFrame(df=table)

    @pytest.fixture
    def make_frame(self) -> FrameFactory:
        """Builds a frame from a dict, so shared tests can create their own data."""
        return lambda data: IbisDataFrame(df=ibis.memtable(pd.DataFrame(dict(data))))

    @pytest.fixture
    def numeric_wrapper(self) -> IbisDataFrame:
        """Five rows with distinct numbers and repeating categories, for sorting and grouping."""
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        table = ibis.memtable(pd.DataFrame(data))
        return IbisDataFrame(df=table)

    def test_count(self, wrapper: IbisDataFrame) -> None:
        """The fixture has two rows, so asking for the count should say 2. It is the
        simplest check that the wrapper really sees the data.
        """
        assert wrapper.count() == 2

    def test_count_empty(self) -> None:
        """A frame with no rows at all should count as 0 instead of blowing up. Empty
        inputs turn up in real pipelines more often than you would think.
        """
        table = ibis.memtable(pd.DataFrame({"a": pd.Series([], dtype="int64")}))
        wrapper = IbisDataFrame(df=table)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: IbisDataFrame) -> None:
        """Collecting rows gives back plain tuples, one per row. That way nothing
        downstream has to know which engine produced them.
        """
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: IbisDataFrame) -> None:
        """We collect the numeric fixture and look at its first two rows. Values and
        column order should come out exactly as they went in.
        """
        result = numeric_wrapper.collect()
        assert result[0] == (1, 10, "A")
        assert result[1] == (2, 20, "B")

    def test_select_single_column(self, wrapper: IbisDataFrame) -> None:
        """Selecting one column by name should leave just that column. Cleaners often
        work on one field at a time, so this is the everyday case.
        """
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: IbisDataFrame) -> None:
        """Asking for two columns keeps those two and drops the rest, email in this
        case. It is how a cleaner narrows a wide table down to what it needs.
        """
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: IbisDataFrame) -> None:
        """Ibis has no built-in idea of first, so we sort by id before taking three
        rows. Then the first and third rows must be the ones we expect.
        """
        result = numeric_wrapper.order_by("id").limit(3)
        assert result.count() == 3
        collected = result.collect()
        assert collected[0] == (1, 10, "A")
        assert collected[2] == (3, 30, "A")

    def test_limit_zero(self, numeric_wrapper: IbisDataFrame) -> None:
        """Asking for zero rows is allowed and simply gives an empty result. Anyone
        computing a limit should not have to special-case zero.
        """
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: IbisDataFrame) -> None:
        """Sorting by value ascending should put 10 first and 50 last. It is the plain
        default, so it has to be right.
        """
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: IbisDataFrame) -> None:
        """Turning desc on flips the same list around, 50 down to 10. Handy when you
        want the biggest values first.
        """
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: IbisDataFrame) -> None:
        """We sort by category and then by value. Rows from the same category stay
        together and ties are broken by the second column, so the first two rows
        both belong to A.
        """
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        categories = [row[2] for row in collected]
        assert categories[0] == "A"
        assert categories[1] == "A"

    def test_strip_single_column(self, wrapper: IbisDataFrame) -> None:
        """Some names in the fixture have stray spaces around them. After stripping
        first_name, rahul and PRIYA should come out clean, because messy input is
        full of stray whitespace.
        """
        result = wrapper.strip("first_name")
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[1][0] == "PRIYA"

    def test_strip_multiple_columns(self, wrapper: IbisDataFrame) -> None:
        """Give strip a list of columns and each one gets trimmed, so both first and
        last names come out tidy.
        """
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][1] == "sharma"

    def test_strip_all_string_columns(self, wrapper: IbisDataFrame) -> None:
        """With no columns named, strip trims every text column and leaves the other
        types alone. rahul and the email address both come back without padding.
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
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
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
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert collected[1][0] is None
        assert collected[1][1] is None

    def test_nullif_all_string_columns(self) -> None:
        """With no columns named, nullif turns the blanks in every text column into
        nulls. Both col1 and col2 have one, and both should go.
        """
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.nullif()
        collected = result.collect()
        assert collected[0][1] is None
        assert collected[1][0] is None

    def test_distinct_all_columns(self) -> None:
        """Two of the three rows are identical in every column. Distinct keeps just one
        of them, so three rows become two.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self) -> None:
        """Col2 differs from row to row, but we only ask about col1. Judged on col1
        alone the first two rows are twins, so we end up with two rows.
        """
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_filter_null_all_columns(self) -> None:
        """One row has a null in col1. With no columns named, a null anywhere removes
        the row, which leaves two.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self) -> None:
        """The null sits in col2 and we ask about col2 only, so that row is dropped and
        two remain. Nulls in columns we did not name would be ignored.
        """
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self) -> None:
        """One row has a null in col1 and another has one in col2. Naming both columns
        drops both rows and leaves a single clean one.
        """
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: IbisDataFrame) -> None:
        """Grouping by category and counting should give at least one group."""
        result = numeric_wrapper.group_by(["category"]).agg(Aggregators.count)
        assert result.count() > 0

    def test_group_by_then_agg_count_produces_real_per_value_counts(self) -> None:
        """Three rows with keys a, a and b should give a with 2 and b with 1. We want
        real counts per group, not one grand total.
        """
        data = {"k": ["a", "a", "b"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.group_by(["k"]).agg(Aggregators.count).order_by("k").collect()
        assert set(result) == {("a", 2), ("b", 1)}

    def test_agg_with_callable(self, numeric_wrapper: IbisDataFrame) -> None:
        """We pass a function that works on an Ibis column, a sum here, and the
        aggregation should return a result.
        """
        agg_config = {"value": lambda x: x.sum()}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0

    def test_rename_cols_direction(self, wrapper: IbisDataFrame) -> None:
        """We rename first_name to fname. The new name must exist, the old one must be
        gone and the data stays put, so the mapping really goes old to new and not
        the other way round.
        """
        wrapper.rename_cols({"first_name": "fname"})
        cols = tuple(name for name, _ in wrapper.cols())
        assert "fname" in cols
        assert "first_name" not in cols
        collected = wrapper.collect()
        assert collected[0][0] == " rahul "

    def test_read_cols_multi_column(self, wrapper: IbisDataFrame) -> None:
        """A reader that takes first and last name is called once per row with both
        values. We just record the calls and expect two of them.
        """
        seen: list[tuple[str, str]] = []

        def reader(first: str, last: str) -> None:
            """Records the values it is given so the test can count calls."""
            seen.append((first, last))

        wrapper.read_cols([DataReader(fn=reader, cols=("first_name", "last_name"))])
        assert len(seen) == 2

    def test_write_cols_constant_literal(self, wrapper: IbisDataFrame) -> None:
        """A writer whose expression is the plain text unknown fills the new status
        column with that value on every row. It is how you stamp a default onto a
        column.
        """
        writer_config = DataWriter(
            expr="unknown",
            read_cols=(),
            write_cols=(("status", DataType.STR),),
        )
        wrapper.write_cols([writer_config])
        collected = wrapper.collect()
        cols = tuple(name for name, _ in wrapper.cols())
        status_idx = cols.index("status")
        assert all(row[status_idx] == "unknown" for row in collected)

    def test_write_cols_multi_output_struct_unpack(
        self, wrapper: IbisDataFrame
    ) -> None:
        """One writer function returns two things, a trimmed name and its length, and
        each lands in its own new column. A single function can feed several
        outputs.
        """

        def split_name(full: str) -> tuple[str, int]:
            """Returns two outputs so the test can check multi-column writes."""
            return full.strip(), len(full.strip())

        writer_config = DataWriter(
            expr=split_name,
            read_cols=("first_name",),
            write_cols=(
                ("clean_first_name", DataType.STR),
                ("first_name_len", DataType.INT),
            ),
        )
        wrapper.write_cols([writer_config])
        collected = wrapper.collect()
        cols = tuple(name for name, _ in wrapper.cols())
        clean_idx = cols.index("clean_first_name")
        len_idx = cols.index("first_name_len")
        assert collected[0][clean_idx] == "rahul"
        assert collected[0][len_idx] == 5
