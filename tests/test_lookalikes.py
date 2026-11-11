import pytest

from dataclean.utils import looks_like_code, looks_like_link, looks_like_path


@pytest.mark.parametrize(
    "text",
    [
        "{{x}}",
        "${x}",
        "%s",
        "a; b",
        "a=b",
        "<%= x %>",
        "select * from t",
        "drop table t",
        "union all select 1",
        "insert into t",
        "delete from t",
        "xxxxxxxx",
    ],
)
def test_looks_like_code(text: str) -> None:
    assert looks_like_code(text)


@pytest.mark.parametrize(
    "text", ["../../etc/passwd", "..\\x", "/etc/passwd", "~/x", "C:\\dir"]
)
def test_looks_like_path(text: str) -> None:
    assert looks_like_path(text)


@pytest.mark.parametrize("text", ["a@b.com", "https://x.com", "ftp://h/x"])
def test_looks_like_link(text: str) -> None:
    assert looks_like_link(text)


PLAIN = [
    "John Smith",
    "AT&T",
    "Select Group",
    "Drop Zone",
    "Dr. Reddy's",
    "M/s X",
    "AC/DC",
    "Aaaron",
    "Mississippi",
]


@pytest.mark.parametrize("text", PLAIN)
def test_plain_text_looks_like_nothing(text: str) -> None:
    assert not (looks_like_code(text) or looks_like_path(text) or looks_like_link(text))


def test_each_check_ignores_the_others() -> None:
    assert not looks_like_code("../x") and not looks_like_link("../x")
    assert not looks_like_path("a@b.com") and not looks_like_code("a@b.com")
    assert not looks_like_path(
        "select * from t".replace("*", "x").replace("select", "x")
    )
