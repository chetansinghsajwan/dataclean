from dataclasses import dataclass

import pytest

from dataclean import EmailCleaner


@dataclass
class Case:
    input: str
    expected: str
    output_format: EmailCleaner.OutputFormat
    lowercase: bool
    keep_tags: bool
    keep_dots: bool


test_cases = [
    Case(
        input=" User.Name+Tag@Gmail.com ",
        expected="user.name+tag@gmail.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="ANOTHER.EMAIL@yahoo.co.in",
        expected="another.email@yahoo.co.in",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="test.email.123@outlook.com",
        expected="test.email.123@outlook.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="John.Doe@gmail.com",
        expected="john.doe@gmail.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input=" admin+support@site.com",
        expected="admin+support@site.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="dots.dots.dots@gmail.com ",
        expected="dots.dots.dots@gmail.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="info@Corporate-Domain.net",
        expected="info@corporate-domain.net",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
    Case(
        input="Jane.Smith+Newsletter@protonmail.com",
        expected="jane.smith+newsletter@protonmail.com",
        output_format=EmailCleaner.OutputFormat.FULL,
        lowercase=True,
        keep_tags=True,
        keep_dots=True,
    ),
]


def test_email_cleaner():

    for test_case in test_cases:
        cleaner = EmailCleaner(
            output_format=test_case.output_format,
            lowercase=test_case.lowercase,
            keep_tags=test_case.keep_tags,
            keep_dots=test_case.keep_dots,
        )

        cleaned_email = cleaner.clean_row(test_case.input)
        assert cleaned_email == test_case.expected, (
            f"Expected '{test_case.expected}' but got '{cleaned_email}' for input '{test_case.input}'"
        )


# ==============================================================================
# EXTRACTION, VALIDATION AND INTERNATIONAL DOMAINS
# ==============================================================================


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("Name <a@b.com>", "a@b.com"),
        ('"Doe, Jo" <a@b.com>', "a@b.com"),
        ("<a@b.com>", "a@b.com"),
        ("mailto:a@b.com", "a@b.com"),
        ("a@b.com (work)", "a@b.com"),
        ("'a@b.com'", "a@b.com"),
        ("a@b.com.", "a@b.com"),
        ("a@b.com;c@d.com", "a@b.com"),
        ("a@b.com, c@d.com", "a@b.com"),
        ("﻿a@b.com​", "a@b.com"),
    ],
)
def test_email_unwraps_common_wrappers(input_value, expected):
    assert EmailCleaner().clean_row(input_value) == expected


@pytest.mark.parametrize(
    "input_value",
    [
        "with space@example.com",
        "see a@b.com",
        '"a b"@c.com',
        "two@@example.com",
        "a@b",
        "a@b.c",
        "not-an-email",
        "<script>@x.com",
        "user@domain,com",
    ],
)
def test_email_text_around_the_address_gives_none(input_value):
    assert EmailCleaner().clean_row(input_value) is None


@pytest.mark.parametrize(
    "input_value",
    [
        "a..b@c.com",
        ".a@b.com",
        "a.@b.com",
        "a@b..com",
        "a@-b.com",
        "a@b-.com",
        "x" * 65 + "@b.com",
        "a@" + "b" * 64 + ".com",
        "a@b." + "c" * 64,
        "a@" + ".".join(["abcdefghi"] * 30) + ".com",
    ],
)
def test_email_strict_rejects_breaking_the_standard(input_value):
    assert EmailCleaner().clean_row(input_value) is None


def test_email_not_strict_keeps_improper_addresses():
    cleaner = EmailCleaner(strict=False)
    assert cleaner.clean_row("a..b@c.com") == "a..b@c.com"
    assert cleaner.clean_row(".a@b.com") == ".a@b.com"
    assert cleaner.clean_row("a@b..com") == "a@b..com"
    assert cleaner.clean_row("x" * 70 + "@b.com") == "x" * 70 + "@b.com"
    assert cleaner.clean_row("with space@example.com") is None
    assert cleaner.clean_row("a@b") is None


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("user@münchen.de", "user@münchen.de"),
        ("Jane@Exämple.com", "jane@exämple.com"),
        ("user@例え.jp", "user@例え.jp"),
        ("user@xn--mnchen-3ya.de", "user@xn--mnchen-3ya.de"),
    ],
)
def test_email_international_domains_are_kept(input_value, expected):
    assert EmailCleaner().clean_row(input_value) == expected
    assert EmailCleaner(strict=False).clean_row(input_value) == expected


def test_email_components_output_for_international_domain():
    cleaner = EmailCleaner(output_format=EmailCleaner.OutputFormat.COMPONENTS)
    assert cleaner.clean_row("a+t@münchen.de") == ("a", "t", "münchen.de")


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("john@gmial.com", "john@gmail.com"),
        ("john@gmail.con", "john@gmail.com"),
        ("john@gmial.con", "john@gmail.com"),
        ("john@Yahooo.com", "john@yahoo.com"),
        ("john@hotmial.com", "john@hotmail.com"),
        ("john@outlok.com", "john@outlook.com"),
        ("john@rediffmial.com", "john@rediffmail.com"),
        ("john@gmail.com", "john@gmail.com"),
        ("john@example.com", "john@example.com"),
        ("john@msn.com", "john@msn.com"),
        ("john@mns.com", "john@msn.com"),
        ("john@gmai.com", "john@gmail.com"),
        ("john@live.co", "john@live.com"),
        ("john@mon.co", "john@mon.co"),
        ("john@aoo.co", "john@aoo.co"),
        ("john@gmail.co.in", "john@gmail.co.in"),
    ],
)
def test_email_fixes_domain_typos_of_known_providers(input_value, expected):
    assert EmailCleaner().clean_row(input_value) == expected


def test_email_domain_typo_fix_can_be_turned_off():
    cleaner = EmailCleaner(fix_domain_typos=False)
    assert cleaner.clean_row("john@gmial.com") == "john@gmial.com"


def test_email_domain_typo_fix_keeps_local_part_and_tag():
    cleaner = EmailCleaner(output_format=EmailCleaner.OutputFormat.COMPONENTS)
    assert cleaner.clean_row("Jo.Hn+x@gmial.com") == ("jo.hn", "x", "gmail.com")


def test_email_cleaner_strips_html_first() -> None:
    cleaner = EmailCleaner()
    assert cleaner.clean_row("<b>John@Example.com</b>") == "john@example.com"
    assert cleaner.clean_row("<script>a@b.com</script>") is None
