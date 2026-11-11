from dataclean.utils import remove_invisible, replace_control_chars


def test_remove_invisible() -> None:
    assert remove_invisible("a\u200bb\ufeffc\u2060d") == "abcd"
    assert remove_invisible("plain text") == "plain text"


def test_replace_control_chars() -> None:
    assert replace_control_chars("a\tb\nc\rd") == "a b c d"
    assert replace_control_chars("a\tb", "") == "ab"
