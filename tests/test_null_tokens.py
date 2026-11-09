import pytest

from dataclean.utils import COMMON_NULL_TOKENS, is_null_token, null_token_set


@pytest.mark.parametrize("value", ["", "null", "NULL", "N/A", "na", "-", "None"])
def test_common_tokens_are_null(value: str) -> None:
    assert is_null_token(value, null_token_set(COMMON_NULL_TOKENS))


def test_a_cleaner_can_choose_its_own_tokens() -> None:
    tokens = null_token_set(("null", "n/a"))

    assert is_null_token("N/A", tokens)
    assert not is_null_token("Na", tokens)
