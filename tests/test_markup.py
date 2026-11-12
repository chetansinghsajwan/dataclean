"""Tests stripping HTML and extracting links from markup in text values."""

import pytest

from dataclean.utils import html_hrefs, strip_html


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
    """Tags and comments are swapped for a space, so the words on either side do not
    stick together.
    """
    assert strip_html(text) == expected


def test_strip_html_replacement() -> None:
    """You can choose what replaces the tags, nothing at all here, and script content
    disappears along with its tag.
    """
    assert strip_html("a<b>c</b><script>x</script>d", "") == "acd"


@pytest.mark.parametrize(
    "text, expected",
    [
        ('<a href="https://x.com">site</a>', ("https://x.com",)),
        ("<A HREF='mailto:a@b.com'>mail</A>", ("mailto:a@b.com",)),
        ("<a href=https://x.com/a>x</a>", ("https://x.com/a",)),
        ('<a class="c" href="/a?x=1&amp;y=2">x</a>', ("/a?x=1&y=2",)),
        ('<a href="a.com">1</a> <a href="b.com">2</a>', ("a.com", "b.com")),
        ('<script><a href="x.com"></a></script>', ()),
        ('<!-- <a href="x.com"> -->', ()),
        ('<a href="">x</a>', ()),
        ("no links", ()),
    ],
)
def test_html_hrefs(text: str, expected: tuple[str, ...]) -> None:
    """Link targets are collected from anchor tags. That way the URLs can be kept even
    after the markup is stripped.
    """
    assert html_hrefs(text) == expected
