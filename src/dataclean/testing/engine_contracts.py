"""Shared pytest contract tests for validating :class:`DataFrame` engine adapters.

Any engine adapter implementing :class:`~dataclean.engine.dataframe.DataFrame`
(e.g. a pandas or PySpark wrapper) can verify it satisfies the expected
contract by subclassing :class:`BaseDataFrameTests` and providing a
``wrapper`` fixture that yields an instance pre-loaded with
:data:`RAW_TEST_DATA`.
"""

import pytest

from dataclean.engine.dataframe import DataFrame, DataReader, DataType, DataWriter

RAW_TEST_DATA: dict[str, list[str]] = {
    "first_name": [" rahul ", " PRIYA "],
    "last_name": ["sharma", "patel"],
    "email": ["rahul+spam@gmail.com", "priya@yahoo.com"],
}
"""Fixture data engine adapter tests should load their ``wrapper`` fixture with."""


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
