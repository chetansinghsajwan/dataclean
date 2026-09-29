from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest

from dataclean import DataFrame


@pytest.fixture
def mock_df_with_value_counts():
    """Factory fixture for mocking the DataFrame chain used by EnumCleaner
    (and its subclasses, e.g. BoolCleaner, GenderCleaner) value-based auto
    matching in ``match_score``: ``select().strip().nullif().filter_null()
    .group_by().agg().order_by().limit().collect()``.

    Returns a builder function that takes an iterable of ``(value, count)``
    rows and produces a mocked DataFrame whose ``.collect()`` call at the end
    of that chain resolves to those rows, bypassing any real dataframe engine.
    """

    def _build(value_counts: Iterable[tuple[Any, int]]) -> MagicMock:
        mock_df = MagicMock(spec=DataFrame)
        chain = mock_df.select.return_value.strip.return_value.nullif.return_value.filter_null.return_value.group_by.return_value.agg.return_value.order_by.return_value.limit.return_value
        chain.collect.return_value = list(value_counts)
        return mock_df

    return _build
