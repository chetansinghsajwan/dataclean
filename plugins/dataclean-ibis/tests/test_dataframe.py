import ibis
import pandas as pd
import pytest
from dataclean_ibis import IbisDataFrame

from dataclean.engine.dataframe import Aggregators, DataReader, DataType, DataWriter
from dataclean.testing import RAW_TEST_DATA, BaseDataFrameTests


class TestIbisDataFrame(BaseDataFrameTests):
    """Invokes the entire reusable test suite specifically for Ibis."""

    @pytest.fixture
    def wrapper(self) -> IbisDataFrame:
        table = ibis.memtable(pd.DataFrame(RAW_TEST_DATA))
        return IbisDataFrame(df=table)

    @pytest.fixture
    def numeric_wrapper(self) -> IbisDataFrame:
        data = {
            "id": [1, 2, 3, 4, 5],
            "value": [10, 20, 30, 40, 50],
            "category": ["A", "B", "A", "B", "C"],
        }
        table = ibis.memtable(pd.DataFrame(data))
        return IbisDataFrame(df=table)

    def test_count(self, wrapper: IbisDataFrame) -> None:
        assert wrapper.count() == 2

    def test_count_empty(self) -> None:
        table = ibis.memtable(pd.DataFrame({"a": pd.Series([], dtype="int64")}))
        wrapper = IbisDataFrame(df=table)
        assert wrapper.count() == 0

    def test_collect(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.collect()
        assert len(result) == 2
        assert all(isinstance(row, tuple) for row in result)

    def test_collect_values_match(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.collect()
        assert result[0] == (1, 10, "A")
        assert result[1] == (2, 20, "B")

    def test_select_single_column(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.select("first_name")
        assert len(result.cols()) == 1
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols

    def test_select_multiple_columns(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.select(["first_name", "last_name"])
        assert len(result.cols()) == 2
        cols = tuple(name for name, _ in result.cols())
        assert "first_name" in cols
        assert "last_name" in cols
        assert "email" not in cols

    def test_limit(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.order_by("id").limit(3)
        assert result.count() == 3
        collected = result.collect()
        assert collected[0] == (1, 10, "A")
        assert collected[2] == (3, 30, "A")

    def test_limit_zero(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.limit(0)
        assert result.count() == 0

    def test_order_by_ascending(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=False)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [10, 20, 30, 40, 50]

    def test_order_by_descending(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.order_by("value", desc=True)
        collected = result.collect()
        values = [row[1] for row in collected]
        assert values == [50, 40, 30, 20, 10]

    def test_order_by_multiple_columns(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.order_by(["category", "value"], desc=False)
        collected = result.collect()
        categories = [row[2] for row in collected]
        assert categories[0] == "A"
        assert categories[1] == "A"

    def test_strip_single_column(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.strip("first_name")
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[1][0] == "PRIYA"

    def test_strip_multiple_columns(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.strip(["first_name", "last_name"])
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][1] == "sharma"

    def test_strip_all_string_columns(self, wrapper: IbisDataFrame) -> None:
        result = wrapper.strip()
        collected = result.collect()
        assert collected[0][0] == "rahul"
        assert collected[0][2] == "rahul+spam@gmail.com"

    def test_nullif_empty_strings(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "y", ""]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.nullif("col1")
        collected = result.collect()
        assert collected[0][0] == "a"
        assert collected[1][0] is None
        assert collected[2][0] == "b"

    def test_nullif_multiple_columns(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["x", "", "z"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.nullif(["col1", "col2"])
        collected = result.collect()
        assert collected[1][0] is None
        assert collected[1][1] is None

    def test_nullif_all_string_columns(self) -> None:
        data = {"col1": ["a", "", "b"], "col2": ["", "y", "z"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.nullif()
        collected = result.collect()
        assert collected[0][1] is None
        assert collected[1][0] is None

    def test_distinct_all_columns(self) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "a", "b"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.distinct()
        assert result.count() == 2

    def test_distinct_specific_columns(self) -> None:
        data = {"col1": [1, 1, 2], "col2": ["a", "b", "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.distinct(["col1"])
        assert result.count() == 2

    def test_filter_null_all_columns(self) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null()
        assert result.count() == 2

    def test_filter_null_specific_columns(self) -> None:
        data = {"col1": [1, 2, 3], "col2": ["a", None, "c"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null("col2")
        assert result.count() == 2

    def test_filter_null_multiple_columns(self) -> None:
        data = {"col1": [1, None, 3], "col2": ["a", "b", None]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.filter_null(["col1", "col2"])
        assert result.count() == 1

    def test_group_by_single_column(self, numeric_wrapper: IbisDataFrame) -> None:
        result = numeric_wrapper.group_by(["category"]).agg(Aggregators.count)
        assert result.count() > 0

    def test_group_by_then_agg_count_produces_real_per_value_counts(self) -> None:
        data = {"k": ["a", "a", "b"]}
        wrapper = IbisDataFrame(df=ibis.memtable(pd.DataFrame(data)))
        result = wrapper.group_by(["k"]).agg(Aggregators.count).order_by("k").collect()
        assert set(result) == {("a", 2), ("b", 1)}

    def test_agg_with_callable(self, numeric_wrapper: IbisDataFrame) -> None:
        agg_config = {"value": lambda x: x.sum()}
        result = numeric_wrapper.agg(agg_config)
        assert result.count() > 0

    def test_rename_cols_direction(self, wrapper: IbisDataFrame) -> None:
        wrapper.rename_cols({"first_name": "fname"})
        cols = tuple(name for name, _ in wrapper.cols())
        assert "fname" in cols
        assert "first_name" not in cols
        collected = wrapper.collect()
        assert collected[0][0] == " rahul "

    def test_read_cols_multi_column(self, wrapper: IbisDataFrame) -> None:
        seen: list[tuple[str, str]] = []

        def reader(first: str, last: str) -> None:
            seen.append((first, last))

        wrapper.read_cols([DataReader(fn=reader, cols=("first_name", "last_name"))])
        assert len(seen) == 2

    def test_write_cols_constant_literal(self, wrapper: IbisDataFrame) -> None:
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
        def split_name(full: str) -> tuple[str, int]:
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
