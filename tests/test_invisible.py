from dataclean.utils import remove_invisible, replace_control_chars


def test_remove_invisible() -> None:
    assert remove_invisible("a\u200bb\ufeffc\u2060d") == "abcd"
    assert remove_invisible("plain text") == "plain text"


def test_remove_invisible_drops_direction_marks_and_overrides() -> None:
    assert remove_invisible("\u202eevil\u202c") == "evil"
    assert remove_invisible("a\u200eb\u200fc\u2066d\u2069") == "abcd"


def test_replace_control_chars() -> None:
    assert replace_control_chars("a\tb\nc\rd") == "a b c d"
    assert replace_control_chars("a\tb", "") == "ab"
