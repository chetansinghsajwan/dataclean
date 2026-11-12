"""Email cleaner tests: normalising, extracting from wrappers, strict validation, international domains and typo repair."""

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
    """We run a set of typical addresses through the cleaner with the standard options. Spaces are trimmed and the text is lowercased, while dots and plus tags stay, so the same address always looks the same."""
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
    """Exports often wrap the address in angle brackets, quotes or a display name. The cleaner should pull out just the plain address."""
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
    """If the cell has extra words, spaces or broken structure, it is not a single clean address. Rather than pick something out, we return null."""
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
    """Double dots, leading hyphens and over-long parts break the email standard and would bounce. In the default strict mode, each of these becomes null."""
    assert EmailCleaner().clean_row(input_value) is None


def test_email_not_strict_keeps_improper_addresses():
    """With strict turned off, odd but readable addresses are kept as they are. Truly unusable ones, like a space in the name part or a domain with no dot, are still dropped."""
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
    """Domains with non-English letters, like a German umlaut, are valid. They should pass through unchanged in both strict and relaxed modes."""
    assert EmailCleaner().clean_row(input_value) == expected
    assert EmailCleaner(strict=False).clean_row(input_value) == expected


def test_email_components_output_for_international_domain():
    """In components mode an address is split into name, tag and domain. This case checks the split works when the domain contains non-English letters."""
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
    """Typing gmial.com instead of gmail.com is a very common mistake. For well-known providers we are confident what was meant, so the domain is corrected."""
    assert EmailCleaner().clean_row(input_value) == expected


def test_email_domain_typo_fix_can_be_turned_off():
    """Some teams do not want their data edited. With the fix off, gmial.com is left exactly as typed."""
    cleaner = EmailCleaner(fix_domain_typos=False)
    assert cleaner.clean_row("john@gmial.com") == "john@gmial.com"


def test_email_domain_typo_fix_keeps_local_part_and_tag():
    """When a domain typo is repaired, only the domain should change. The name part is lowercased as usual and the tag stays."""
    cleaner = EmailCleaner(output_format=EmailCleaner.OutputFormat.COMPONENTS)
    assert cleaner.clean_row("Jo.Hn+x@gmial.com") == ("jo.hn", "x", "gmail.com")


def test_email_cleaner_strips_html_first() -> None:
    """Addresses sometimes arrive wrapped in HTML. Plain formatting tags are dropped, but script content is never trusted and gives null."""
    cleaner = EmailCleaner()
    assert cleaner.clean_row("<b>John@Example.com</b>") == "john@example.com"
    assert cleaner.clean_row("<script>a@b.com</script>") is None


def test_email_cleaner_reads_mailto_links_first() -> None:
    """In an anchor tag, the mailto target is the real address and the visible text may say anything. So we read the link first and only fall back to the text when there is no usable mailto."""
    cleaner = EmailCleaner()
    assert cleaner.clean_row('<a href="mailto:Jane@Example.com">click</a>') == (
        "jane@example.com"
    )
    assert cleaner.clean_row('<a href="mailto:a@b.com?subject=Hi">x@y.com</a>') == (
        "a@b.com"
    )
    # Without a usable mailto link, the text is used.
    assert cleaner.clean_row('<a href="/contact">x@y.com</a>') == "x@y.com"


def test_email_clean_strips_emoji():
    """Someone put an envelope emoji in front of the address. We drop it and clean the rest as normal."""
    assert EmailCleaner().clean_row("\U0001f4e7 John@Example.com") == "john@example.com"
