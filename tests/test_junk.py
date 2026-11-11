import pytest

from dataclean.utils import looks_like_junk


@pytest.mark.parametrize(
    "text",
    [
        "a@b.com",
        "https://x.com",
        "{{x}}",
        "${x}",
        "%s",
        "a; b",
        "a=b",
        "select * from t",
        "drop table t",
        "union all select 1",
        "insert into t",
        "delete from t",
        "C:\\dir",
        "xxxxxxxx",
    ],
)
def test_looks_like_junk(text: str) -> None:
    assert looks_like_junk(text)


@pytest.mark.parametrize(
    "text",
    [
        "John Smith",
        "AT&T",
        "Select Group",
        "Drop Zone",
        "Dr. Reddy's",
        "M/s X",
        "Aaaron",
        "Mississippi",
    ],
)
def test_plain_text_is_not_junk(text: str) -> None:
    assert not looks_like_junk(text)
