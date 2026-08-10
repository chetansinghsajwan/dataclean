import pytest

from dataclean.engine.dataframe import DataFrame, DataReader, DataType, DataWriter

RAW_TEST_DATA: dict[str, list[str]] = {
    "first_name": [" rahul ", " PRIYA "],
    "last_name": ["sharma", "patel"],
    "email": ["rahul+spam@gmail.com", "priya@yahoo.com"],
}


class BaseDataFrameTests:
    @pytest.fixture
    def wrapper(self) -> DataFrame:
        raise NotImplementedError("Subclasses must implement the 'wrapper' fixture.")

    def test_supports_validation(self, wrapper: DataFrame) -> None:
        assert type(wrapper).supports(wrapper.df) is True
        assert type(wrapper).supports(["not", "a", "dataframe"]) is False

    def test_cols_retrieval(self, wrapper: DataFrame) -> None:
        expected_keys = tuple(RAW_TEST_DATA.keys())
        active_names = tuple(name for name, _ in wrapper.cols())
        assert active_names == expected_keys

    def test_rename_cols(self, wrapper: DataFrame) -> None:
        rename_map = {"first_name": "fname", "last_name": "lname"}
        wrapper.rename_cols(rename_map)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "fname" in active_names, active_names
        assert "lname" in active_names, active_names
        assert "first_name" not in active_names, active_names

    def test_write_cols_via_multi_arg_unpacking(self, wrapper: DataFrame) -> None:
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
        def mock_reader(first: str, email: str) -> None:
            del first, email

        reader_config = DataReader(fn=mock_reader, cols=("first_name", "email"))
        starting_cols = wrapper.cols()

        wrapper.read_cols([reader_config])
        assert wrapper.cols() == starting_cols

    def test_read_single_col_fallback_macro(self, wrapper: DataFrame) -> None:
        def single_col_verifier(val: str) -> None:
            del val

        reader_config = DataReader(fn=single_col_verifier, cols=("email",))
        wrapper.read_cols([reader_config])

    def test_remove_cols(self, wrapper: DataFrame) -> None:
        cols_to_drop = ["last_name", "email"]
        wrapper.remove_cols(cols_to_drop)

        active_names = tuple(name for name, _ in wrapper.cols())
        assert "first_name" in active_names
        assert "last_name" not in active_names
        assert "email" not in active_names

    def test_cast_cols_updates_metadata_types(self, wrapper: DataFrame) -> None:
        wrapper.cast_cols({"first_name": DataType.STR})
        type_map = dict(wrapper.cols())
        assert type_map["first_name"] == DataType.STR
