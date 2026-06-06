from dataclean.col_renamer import ColRenamer

test_cases = [
    # ==========================================
    # snake
    # ==========================================
    {
        "input": "First Name",
        "expected": "first_name",
        "case": "snake",
    },
    {
        "input": "first_name",
        "expected": "first_name",
        "case": "snake",
    },
    # ==========================================
    # upper_snake
    # ==========================================
    {
        "input": "First Name",
        "expected": "FIRST_NAME",
        "case": "upper_snake",
    },
    {
        "input": "FIRST_NAME",
        "expected": "FIRST_NAME",
        "case": "upper_snake",
    },
    # ==========================================
    # upper
    # ==========================================
    {
        "input": "First Name",
        "expected": "FIRSTNAME",
        "case": "upper",
    },
    {
        "input": "FIRST NAME",
        "expected": "FIRSTNAME",
        "case": "upper",
    },
    # ==========================================
    # lower
    # ==========================================
    {
        "input": "First Name",
        "expected": "firstname",
        "case": "lower",
    },
    {
        "input": "first name",
        "expected": "firstname",
        "case": "lower",
    },
    # ==========================================
    # pascal
    # ==========================================
    {
        "input": "First Name",
        "expected": "FirstName",
        "case": "pascal",
    },
    {
        "input": "FirstName",
        "expected": "FirstName",
        "case": "pascal",
    },
    # ==========================================
    # camel
    # ==========================================
    {
        "input": "First Name",
        "expected": "firstName",
        "case": "camel",
    },
    {
        "input": "firstName",
        "expected": "firstName",
        "case": "camel",
    },
    # ==========================================
    # kebab
    # ==========================================
    {
        "input": "First Name",
        "expected": "first-name",
        "case": "kebab",
    },
    {
        "input": "first-name",
        "expected": "first-name",
        "case": "kebab",
    },
    # ==========================================
    # train
    # ==========================================
    {
        "input": "First Name",
        "expected": "First-Name",
        "case": "train",
    },
    {
        "input": "First-Name",
        "expected": "First-Name",
        "case": "train",
    },
    # ==========================================
    # cobol
    # ==========================================
    {
        "input": "First Name",
        "expected": "FIRST-NAME",
        "case": "cobol",
    },
    {
        "input": "FIRST-NAME",
        "expected": "FIRST-NAME",
        "case": "cobol",
    },
]


def test_col_renamer():

    for case in test_cases:
        renamer = ColRenamer(case["case"])
        result = renamer.rename(case["input"])

        assert result == case["expected"], (
            f"Failed for case: {case['case']}, input: {case['input']}, expected: {case['expected']}, got: {result}"
        )
