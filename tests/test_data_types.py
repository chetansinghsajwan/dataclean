"""Tests for the engine-agnostic DataType enum."""

from dataclean.engine import DataType


def test_temporal_types_exist_with_lowercase_values() -> None:
    assert DataType.DATE == "date"
    assert DataType.DATETIME == "datetime"
    assert DataType.TIME == "time"


def test_all_members_render_as_their_plain_value() -> None:
    assert {repr(member) for member in DataType} == {
        member.value for member in DataType
    }
