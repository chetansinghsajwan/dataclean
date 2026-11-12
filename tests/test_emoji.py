"""Tests for the emoji remover."""

import pytest

from dataclean.utils import remove_emoji


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("John \U0001f600 Smith", "John  Smith"),
        ("Rahul\u2764\ufe0f", "Rahul"),
        ("Asha \U0001f469\U0001f3fd\u200d\U0001f4bb", "Asha "),
        ("family \U0001f468\u200d\U0001f469\u200d\U0001f467", "family "),
        ("India \U0001f1ee\U0001f1f3", "India "),
        ("England \U0001f3f4\U000e0067\U000e0062\U000e007f", "England "),
        ("call 1\ufe0f\u20e3 now", "call  now"),
        ("\u2705 done \u2b50", " done "),
        ("\U0001f680\U0001f680", ""),
    ],
)
def test_remove_emoji_removes_emoji(raw: str, expected: str) -> None:
    assert remove_emoji(raw) == expected


@pytest.mark.parametrize(
    "value",
    [
        "Plain text",
        "AT&T \u00a9 2020 \u00ae \u2122",
        "Room #4, 5*",
        "A \u2192 B \u2318 \u25a0",
        "\u0915\u094d\u200d\u0937",  # Devanagari with a zero-width joiner
        "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",  # Persian, non-joiner
        "Zo\u00eb Mu\u00f1oz \u00c5ngstr\u00f6m \u5f20\u4f1f",
        "",
    ],
)
def test_remove_emoji_keeps_other_text(value: str) -> None:
    assert remove_emoji(value) == value
