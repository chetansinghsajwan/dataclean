"""Tests removal of invisible characters and control-character replacement."""

from dataclean.utils import remove_invisible, replace_control_chars


def test_remove_invisible() -> None:
    """Zero-width spaces, byte order marks and word joiners hide inside text and break
    matching. We remove them, and plain text is left as it is.
    """
    assert remove_invisible("a\u200bb\ufeffc\u2060d") == "abcd"
    assert remove_invisible("plain text") == "plain text"


def test_remove_invisible_drops_direction_marks_and_overrides() -> None:
    """Text-direction marks and overrides go too. They can make text display in a
    different order than it is stored, which is a known way to disguise things.
    """
    assert remove_invisible("\u202eevil\u202c") == "evil"
    assert remove_invisible("a\u200eb\u200fc\u2066d\u2069") == "abcd"


def test_replace_control_chars() -> None:
    """Tabs, newlines and carriage returns turn into a space, or whatever replacement
    you choose. That keeps each value on one line.
    """
    assert replace_control_chars("a\tb\nc\rd") == "a b c d"
    assert replace_control_chars("a\tb", "") == "ab"
