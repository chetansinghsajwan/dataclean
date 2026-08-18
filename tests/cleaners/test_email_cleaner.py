from dataclasses import dataclass

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
