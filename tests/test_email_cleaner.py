from src.dataclean.cleaners.email_cleaner import EmailCleaner

test_cases = [
    {
        "input": " User.Name+Tag@Gmail.com ",
        "expected": "user.name+tag@gmail.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": "ANOTHER.EMAIL@yahoo.co.in",
        "expected": "another.email@yahoo.co.in",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": "test.email.123@outlook.com",
        "expected": "test.email.123@outlook.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": "John.Doe@gmail.com",
        "expected": "john.doe@gmail.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": " admin+support@site.com",
        "expected": "admin+support@site.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": " dots.dots.dots@gmail.com ",
        "expected": "dots.dots.dots@gmail.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": "info@Corporate-Domain.net",
        "expected": "info@corporate-domain.net",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
    {
        "input": "Jane.Smith+Newsletter@protonmail.com",
        "expected": "jane.smith+newsletter@protonmail.com",
        "split_components": False,
        "lowercase": True,
        "keep_tags": True,
        "keep_dots": True,
    },
]


def test_email_cleaner():

    for test_case in test_cases:
        cleaner = EmailCleaner(
            split_components=test_case["split_components"],
            lowercase=test_case["lowercase"],
            keep_tags=test_case["keep_tags"],
            keep_dots=test_case["keep_dots"],
        )

        cleaned_email = cleaner.clean_value(test_case["input"])
        assert cleaned_email == test_case["expected"], (
            f"Expected '{test_case['expected']}' but got '{cleaned_email}' for input '{test_case['input']}'"
        )
