"""Tests for the engine-agnostic DataType enum."""

from dataclean.engine import DataType


def test_temporal_types_exist_with_lowercase_values() -> None:
    """Date, datetime and time types exist and equal their lowercase names. Config
    files spell them that way, so they have to match.
    """
    assert DataType.DATE == "date"
    assert DataType.DATETIME == "datetime"
    assert DataType.TIME == "time"


def test_all_members_render_as_their_plain_value() -> None:
    """A DataType member prints as its plain value, like date, and not as
    DataType.DATE. Logs and schemas then read naturally.
    """
    assert {repr(member) for member in DataType} == {
        member.value for member in DataType
    }
