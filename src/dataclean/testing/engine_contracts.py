"""Shared pytest contract tests for validating :class:`DataFrame` engine adapters.

Any engine adapter implementing :class:`~dataclean.engine.dataframe.DataFrame`
(e.g. a pandas or PySpark wrapper) can verify it satisfies the expected
contract by subclassing :class:`BaseDataFrameTests` and providing two
fixtures: ``wrapper``, which yields an instance pre-loaded with
:data:`RAW_TEST_DATA`, and ``make_frame``, a factory that builds an instance
from a ``{column: values}`` mapping.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

import pytest

from dataclean.engine.dataframe import (
    Aggregators,
    DataFrame,
    DataReader,
    DataType,
    DataTypeValues,
    DataWriter,
)

RAW_TEST_DATA: dict[str, list[str]] = {
    "first_name": [" rahul ", " PRIYA "],
    "last_name": ["sharma", "patel"],
    "email": ["rahul+spam@gmail.com", "priya@yahoo.com"],
}
"""Fixture data engine adapter tests should load their ``wrapper`` fixture with."""

FrameFactory = Callable[[Mapping[str, Sequence[DataTypeValues]]], DataFrame]
"""Builds a :class:`DataFrame` of the engine under test from column data."""


def _is_null(value: object) -> bool:
    """Return whether ``value`` is a null in any engine (``None`` or NaN)."""
    return value is None or value != value  # noqa: PLR0124


def _column(df: DataFrame, name: str) -> list[object]:
    """Return the collected values of column ``name``, in row order."""
    index = [col for col, _ in df.cols()].index(name)
    return [row[index] for row in df.collect()]


class BaseDataFrameTests:
    """Mixin of contract tests every :class:`DataFrame` engine adapter must pass.

    Subclass this in an engine adapter's test module and implement the
    ``wrapper`` fixture to run the full contract suite against that engine.
    """

    @pytest.fixture
    def wrapper(self) -> DataFrame:
        """Yield a :class:`DataFrame` instance wrapping :data:`RAW_TEST_DATA`.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.
        """
        raise NotImplementedError("Subclasses must implement the 'wrapper' fixture.")

    @pytest.fixture
    def make_frame(self) -> FrameFactory:
        """Yield a factory building a :class:`DataFrame` from column data.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.
        """
        raise NotImplementedError("Subclasses must implement the 'make_frame' fixture.")

    def test_supports_validation(self, wrapper: DataFrame) -> None:
        """Verify ``supports()`` accepts the wrapped dataframe and rejects non-dataframes."""
        assert type(wrapper).supports(wrapper.df) is True
        assert type(wrapper).supports(["not", "a", "dataframe"]) is False

    def test_cols_retrieval(self, wrapper: DataFrame) -> None:
        """Verify ``cols()`` reports the expected column names in order."""
        expected_keys = tuple(RAW_TEST_DATA.keys())
        active_names = tuple(name for name, _ in wrapper.cols())
        assert active_names == expected_keys

    def test_rename_cols(self, wrapper: DataFrame) -> None:
        """Verify ``rename_cols()`` renames columns and removes the old names."""
        rename_map = {"first_name": "fname", "last_name": "lname"}
        wrapper.rename_cols(rename_map)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "fname" in active_names, active_names
        assert "lname" in active_names, active_names
        assert "first_name" not in active_names, active_names

    def test_write_cols_via_multi_arg_unpacking(self, wrapper: DataFrame) -> None:
        """Verify ``write_cols()`` calls its expr with each read column unpacked positionally."""

        def mock_builder(first: str, last: str) -> str:
            return f"{first.strip().capitalize()} {last.strip().upper()}"

        writer_config = DataWriter(
            expr=mock_builder,
            read_cols=("first_name", "last_name"),
            write_cols=(("full_name", DataType.STR),),
        )

        wrapper.write_cols([writer_config])

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "full_name" in active_names

    def test_read_cols_without_mutating_state(self, wrapper: DataFrame) -> None:
        """Verify ``read_cols()`` invokes its callback without altering the dataframe's columns."""

        def mock_reader(first: str, email: str) -> None:
            del first, email

        reader_config = DataReader(fn=mock_reader, cols=("first_name", "email"))
        starting_cols = wrapper.cols()

        wrapper.read_cols([reader_config])
        assert wrapper.cols() == starting_cols

    def test_read_single_col_fallback_macro(self, wrapper: DataFrame) -> None:
        """Verify ``read_cols()`` works with a reader configured for a single column."""

        def single_col_verifier(val: str) -> None:
            del val

        reader_config = DataReader(fn=single_col_verifier, cols=("email",))
        wrapper.read_cols([reader_config])

    def test_remove_cols(self, wrapper: DataFrame) -> None:
        """Verify ``remove_cols()`` drops exactly the requested columns."""
        cols_to_drop = ["last_name", "email"]
        wrapper.remove_cols(cols_to_drop)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "first_name" in active_names
        assert "last_name" not in active_names
        assert "email" not in active_names

    def test_cast_cols_updates_metadata_types(self, wrapper: DataFrame) -> None:
        """Verify ``cast_cols()`` updates the reported :class:`DataType` for a column."""
        wrapper.cast_cols({"first_name": DataType.STR})
        type_map = dict(wrapper.cols())
        assert type_map["first_name"] == DataType.STR

    def test_datetime_values_are_reported_as_datetime(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify a column of datetimes reports :attr:`DataType.DATETIME`."""
        df = make_frame({"ts": [datetime(2024, 1, 2, 3, 4, 5), datetime(2025, 6, 7)]})
        assert dict(df.cols())["ts"] == DataType.DATETIME

    def test_cast_cols_to_datetime(self, make_frame: FrameFactory) -> None:
        """Verify ``cast_cols()`` can turn ISO strings into a datetime column."""
        df = make_frame({"ts": ["2024-01-02 03:04:05", "2025-06-07 00:00:00"]})
        assert dict(df.cols())["ts"] == DataType.STR

        df.cast_cols({"ts": DataType.DATETIME})

        assert dict(df.cols())["ts"] == DataType.DATETIME

    def test_untouched_datetime_column_keeps_its_type_across_writes(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify writing another column does not change a datetime column's type."""
        df = make_frame({"ts": [datetime(2024, 1, 2)], "a": ["x"]})
        df.write_cols(
            [DataWriter(str.upper, read_cols=("a",), write_cols=(("a", DataType.STR),))]
        )
        assert dict(df.cols())["ts"] == DataType.DATETIME

    # -- shape and materialization ------------------------------------

    def test_count_returns_row_count(self, make_frame: FrameFactory) -> None:
        """Verify ``count()`` returns the number of rows."""
        assert make_frame({"a": [1, 2, 3]}).count() == 3

    def test_count_after_limit_zero(self, make_frame: FrameFactory) -> None:
        """Verify an empty result counts as zero rows."""
        assert make_frame({"a": [1, 2, 3]}).limit(0).count() == 0

    def test_collect_returns_row_tuples_in_column_order(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify ``collect()`` returns one tuple per row, in column order."""
        rows = make_frame({"id": [1, 2], "name": ["a", "b"]}).collect()
        assert rows == [(1, "a"), (2, "b")]

    def test_select_single_and_multiple(self, make_frame: FrameFactory) -> None:
        """Verify ``select()`` keeps only the requested columns."""
        df = make_frame({"a": [1], "b": ["x"], "c": ["y"]})
        assert [c for c, _ in df.select("a").cols()] == ["a"]
        assert [c for c, _ in df.select(["a", "c"]).cols()] == ["a", "c"]
        assert df.select(["a", "c"]).collect() == [(1, "y")]

    def test_limit_keeps_at_most_n_rows(self, make_frame: FrameFactory) -> None:
        """Verify ``limit(n)`` keeps at most ``n`` rows."""
        df = make_frame({"a": [1, 2, 3, 4]})
        assert df.order_by("a").limit(2).collect() == [(1,), (2,)]
        assert df.limit(10).count() == 4

    # -- ordering and uniqueness --------------------------------------

    def test_order_by_ascending_and_descending(self, make_frame: FrameFactory) -> None:
        """Verify ``order_by()`` sorts ascending by default and descending on request."""
        df = make_frame({"a": [3, 1, 2]})
        assert _column(df.order_by("a"), "a") == [1, 2, 3]
        assert _column(df.order_by("a", desc=True), "a") == [3, 2, 1]

    def test_order_by_sorts_by_multiple_columns(self, make_frame: FrameFactory) -> None:
        """Verify ``order_by()`` sorts by several columns in priority order."""
        df = make_frame({"k": ["b", "a", "b", "a"], "v": [1, 2, 0, 1]})
        assert df.order_by(["k", "v"]).collect() == [
            ("a", 1),
            ("a", 2),
            ("b", 0),
            ("b", 1),
        ]

    def test_distinct_removes_duplicate_rows(self, make_frame: FrameFactory) -> None:
        """Verify ``distinct()`` removes fully duplicated rows."""
        df = make_frame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
        assert df.distinct().count() == 2

    def test_distinct_cols_keeps_one_row_per_value(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify ``distinct(cols)`` keeps one row per unique value of ``cols``."""
        df = make_frame({"a": [1, 1, 2], "b": ["x", "y", "z"]})
        result = df.distinct(["a"])
        assert result.count() == 2
        assert sorted(_column(result, "a")) == [1, 2]  # type: ignore[type-var]

    # -- strip / nullif -----------------------------------------------

    def test_strip_named_columns(self, make_frame: FrameFactory) -> None:
        """Verify ``strip(cols)`` strips whitespace only from the named columns."""
        df = make_frame({"a": [" x "], "b": [" y "]})
        assert df.strip("a").collect() == [("x", " y ")]
        assert df.strip(["a", "b"]).collect() == [("x", "y")]

    def test_strip_all_leaves_non_string_columns_alone(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify ``strip()`` with no columns affects strings and ignores other types."""
        df = make_frame({"s": [" x "], "n": [5]})
        assert df.strip().collect() == [("x", 5)]

    def test_strip_named_non_string_column_is_a_no_op(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify naming a non-string column in ``strip(cols)`` leaves it unchanged."""
        df = make_frame({"s": [" x "], "n": [5]})
        assert df.strip(["s", "n"]).collect() == [("x", 5)]

    def test_nullif_named_columns(self, make_frame: FrameFactory) -> None:
        """Verify ``nullif(cols)`` turns empty strings into nulls in the named columns."""
        df = make_frame({"a": ["x", ""], "b": ["", "y"]})
        result = df.nullif("a")
        assert _column(result, "a")[0] == "x"
        assert _is_null(_column(result, "a")[1])
        assert _column(result, "b")[0] == ""

    def test_nullif_all_leaves_non_string_columns_alone(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify ``nullif()`` with no columns affects strings and ignores other types."""
        df = make_frame({"s": ["", "y"], "n": [0, 1]})
        result = df.nullif()
        assert _is_null(_column(result, "s")[0])
        assert _column(result, "n") == [0, 1]

    def test_nullif_named_non_string_column_is_a_no_op(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify naming a non-string column in ``nullif(cols)`` leaves it unchanged."""
        df = make_frame({"s": ["", "y"], "n": [0, 1]})
        assert _column(df.nullif(["n"]), "n") == [0, 1]

    # -- nulls, grouping ----------------------------------------------

    def test_filter_null_all_and_specific_columns(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify ``filter_null()`` drops rows with a null in the checked columns."""
        df = make_frame({"a": ["x", None, "z"], "b": ["p", "q", None]})
        assert df.filter_null().count() == 1
        assert df.filter_null("a").count() == 2
        assert df.filter_null(["a", "b"]).count() == 1

    def test_group_by_agg_count(self, make_frame: FrameFactory) -> None:
        """Verify ``group_by().agg(count)`` yields one (key, count) row per group."""
        df = make_frame({"k": ["a", "a", "b"]})
        result = df.group_by(["k"]).agg(Aggregators.count)
        assert set(result.collect()) == {("a", 2), ("b", 1)}

    # -- write_cols / read_cols ---------------------------------------

    def test_write_cols_fn_sees_none_or_str_and_may_return_none(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify null inputs reach ``expr`` as ``None`` (never NaN) and ``None`` can be returned."""
        seen: list[object] = []

        def fn(value: str | None) -> str | None:
            seen.append(value)
            return None if value is None else value.upper()

        df = make_frame({"a": ["x", None]})
        df.write_cols(
            [DataWriter(fn, read_cols=("a",), write_cols=(("b", DataType.STR),))]
        )

        assert all(v is None or isinstance(v, str) for v in seen), seen
        out = _column(df, "b")
        assert out[0] == "X"
        assert _is_null(out[1])

    def test_write_cols_multiple_outputs(self, make_frame: FrameFactory) -> None:
        """Verify a tuple result is spread across the write columns in order."""

        def fn(value: str) -> tuple[str, int]:
            return value.strip(), len(value.strip())

        df = make_frame({"a": [" ab "]})
        df.write_cols(
            [
                DataWriter(
                    fn,
                    read_cols=("a",),
                    write_cols=(("s", DataType.STR), ("n", DataType.INT)),
                )
            ]
        )
        assert _column(df, "s") == ["ab"]
        assert _column(df, "n") == [2]

    def test_write_cols_multiple_outputs_when_fn_returns_none(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify returning ``None`` from a multi-output ``expr`` nulls every write column."""

        def fn(value: str) -> tuple[str, str] | None:
            return None if value == "bad" else (value, value)

        df = make_frame({"a": ["ok", "bad"]})
        df.write_cols(
            [
                DataWriter(
                    fn,
                    read_cols=("a",),
                    write_cols=(("s", DataType.STR), ("n", DataType.STR)),
                )
            ]
        )
        assert _column(df, "s")[0] == "ok"
        assert _is_null(_column(df, "s")[1])
        assert _is_null(_column(df, "n")[1])

    def test_write_cols_constant_scalar(self, make_frame: FrameFactory) -> None:
        """Verify a constant scalar ``expr`` is broadcast to every row."""
        df = make_frame({"a": ["x", "y"]})
        df.write_cols(
            [DataWriter("k", read_cols=(), write_cols=(("c", DataType.STR),))]
        )
        assert _column(df, "c") == ["k", "k"]

    def test_write_cols_constant_tuple(self, make_frame: FrameFactory) -> None:
        """Verify a constant tuple ``expr`` sends each element to its write column."""
        df = make_frame({"a": ["x", "y"]})
        df.write_cols(
            [
                DataWriter(
                    ("p", "q"),
                    read_cols=(),
                    write_cols=(("c1", DataType.STR), ("c2", DataType.STR)),
                )
            ]
        )
        assert _column(df, "c1") == ["p", "p"]
        assert _column(df, "c2") == ["q", "q"]

    def test_write_cols_overwrites_existing_column(
        self, make_frame: FrameFactory
    ) -> None:
        """Verify writing to an existing column replaces its values."""
        df = make_frame({"a": ["x", "y"]})
        df.write_cols(
            [
                DataWriter(
                    lambda v: v.upper(),
                    read_cols=("a",),
                    write_cols=(("a", DataType.STR),),
                )
            ]
        )
        assert _column(df, "a") == ["X", "Y"]

    def test_read_cols_sees_none_or_str_per_row(self, make_frame: FrameFactory) -> None:
        """Verify ``read_cols()`` calls ``fn`` once per row with ``None`` for nulls."""
        seen: list[object] = []
        df = make_frame({"a": ["x", None]})
        df.read_cols([DataReader(fn=seen.append, cols=("a",))])

        assert len(seen) == 2
        assert all(v is None or isinstance(v, str) for v in seen), seen
