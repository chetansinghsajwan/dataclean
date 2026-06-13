from typing import Any

import pytest

from dataclean.engine.dataframe import DataFrame, DataReader, DataWriter

RAW_TEST_DATA = {
    "first_name": [" rahul ", " PRIYA "],
    "last_name": ["sharma", "patel"],
    "email": ["rahul+spam@gmail.com", "priya@yahoo.com"],
}


class BaseDataFrameTests:
    """
    Reusable abstract test suite. Contains no engine-specific code.
    Any class inheriting from this must implement the 'wrapper' fixture.
    """

    @pytest.fixture
    def wrapper(self) -> Any:
        """
        Abstract fixture to be overridden by child classes.
        """

        raise NotImplementedError("Subclasses must implement the 'wrapper' fixture.")

    def test_supports_validation(self, wrapper: DataFrame):
        """
        Verifies that the static method identifies correct DataFrame types.
        """

        assert type(wrapper).supports(wrapper.df) is True
        assert type(wrapper).supports(["not", "a", "dataframe"]) is False

    def test_cols_retrieval(self, wrapper: DataFrame):
        """
        Ensures that the cols metadata property matches the active dataset exactly.
        """

        expected_keys = tuple(RAW_TEST_DATA.keys())
        # Unpack names from the nested (name, type) tuples
        active_names = tuple(name for name, _ in wrapper.cols())
        assert active_names == expected_keys

    def test_rename_cols(self, wrapper: DataFrame):
        """
        Validates cross-engine column mapping operations rewrite underlying metadata state.
        """

        rename_map = {"first_name": "fname", "last_name": "lname"}
        wrapper.rename_cols(rename_map)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "fname" in active_names, active_names
        assert "lname" in active_names, active_names
        assert "first_name" not in active_names, active_names

    def test_write_cols_via_multi_arg_unpacking(self, wrapper: DataFrame):
        """
        Evaluates writing columns using the concrete DataWriter dataclass container contract.
        """

        def mock_builder(first: str, last: str) -> str:
            return f"{first.strip().capitalize()} {last.strip().upper()}"

        # Build an explicit DataWriter instance matching your schema contract rules
        writer_config = DataWriter(
            expr=mock_builder,
            read_cols=("first_name", "last_name"),
            write_cols=(("full_name", "str"),),
        )

        wrapper.write_cols([writer_config])

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "full_name" in active_names

    def test_read_cols_without_mutating_state(self, wrapper: DataFrame):
        """
        Validates the read execution pipelines execute successfully without mutating state.
        """

        def mock_reader(first: str, email: str) -> None:
            pass

        # Build an explicit DataReader instance matching your schema contract rules
        reader_config = DataReader(fn=mock_reader, cols=("first_name", "email"))

        starting_cols = wrapper.cols()

        wrapper.read_cols([reader_config])
        assert wrapper.cols() == starting_cols

    def test_read_single_col_fallback_macro(self, wrapper: DataFrame):
        """
        Verifies the base class concrete macro `read_col` routes elements correctly.
        """

        def single_col_verifier(val: str) -> None:
            pass

        # Passes a structured DataReader token signature down to the wrapper hook
        reader_config = DataReader(fn=single_col_verifier, cols=("email",))
        wrapper.read_cols([reader_config])

    def test_remove_cols(self, wrapper: DataFrame):
        """
        Ensures targeted deletion pipelines clean up correct data structures cleanly.
        """

        cols_to_drop = ["last_name", "email"]
        wrapper.remove_cols(cols_to_drop)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "first_name" in active_names
        assert "last_name" not in active_names
        assert "email" not in active_names

    def test_cast_cols_updates_metadata_types(self, wrapper: DataFrame):
        """
        Verifies that casting columns updates the metadata DataType literal correctly.
        """

        # Force a type cast conversion on a column
        wrapper.cast_cols({"first_name": "str"})

        # Pull type dictionary out of metadata array cache
        type_map = {name: dt for name, dt in wrapper.cols()}
        assert type_map["first_name"] == "str"
