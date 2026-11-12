"""Tests recognising text placeholders such as N/A that really mean a missing value."""

import pytest

from dataclean.utils import COMMON_NULL_TOKENS, is_null_token, null_token_set


@pytest.mark.parametrize("value", ["", "null", "NULL", "N/A", "na", "-", "None"])
def test_common_tokens_are_null(value: str) -> None:
    """Everyday placeholders such as blank, null, N/A and a dash count as null,
    whatever the case. Real data is full of these.
    """
    assert is_null_token(value, null_token_set(COMMON_NULL_TOKENS))


def test_a_cleaner_can_choose_its_own_tokens() -> None:
    """A cleaner can supply its own token list. With only null and n/a chosen, N/A
    matches but Na does not, since Na could be a real value.
    """
    tokens = null_token_set(("null", "n/a"))

    assert is_null_token("N/A", tokens)
    assert not is_null_token("Na", tokens)
