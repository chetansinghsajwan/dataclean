import pytest

from dataclean.utils import strip_html


@pytest.mark.parametrize(
    "text, expected",
    [
        ("<h1>Title</h1>", " Title "),
        ('<a href="x">link</a>', " link "),
        ("a<br/>b", "a b"),
        ("<!-- note -->kept", " kept"),
        ("<!DOCTYPE html>text", " text"),
        # Code and hidden data go with their tags.
        ("<script>alert(1)</script>after", " after"),
        ("x<SCRIPT type='a'>\nvar a;\n</Script >y", "x y"),
        ("<style>p { color: red }</style><p>hi</p>", "  hi "),
        ("before<script>never closed", "before "),
        ("<!-- <script> -->text", " text"),
        # Not tags.
        ("if a < b and c > d", "if a < b and c > d"),
        ("x<5 and y>3", "x<5 and y>3"),
        ("<https://x.com>", "<https://x.com>"),
        ("Name <john@example.com>", "Name <john@example.com>"),
        ("<www.x.com>", "<www.x.com>"),
        # A tag that only starts with a dropped name is an ordinary tag.
        ("<scripture>psalm</scripture>", " psalm "),
        ("a &amp; b", "a &amp; b"),
    ],
)
def test_strip_html(text: str, expected: str) -> None:
    assert strip_html(text) == expected


def test_strip_html_replacement() -> None:
    assert strip_html("a<b>c</b><script>x</script>d", "") == "acd"
