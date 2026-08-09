from dataclasses import dataclass

from dataclean.col_renamer import ColRenamer


@dataclass
class Case:
    input: str
    expected: str
    case: ColRenamer.CaseTypes


test_cases = [
    # ==========================================
    # snake
    # ==========================================
    Case(
        input="First Name",
        expected="first_name",
        case="snake",
    ),
    Case(
        input="first_name",
        expected="first_name",
        case="snake",
    ),
    # ==========================================
    # upper_snake
    # ==========================================
    Case(
        input="First Name",
        expected="FIRST_NAME",
        case="upper_snake",
    ),
    Case(
        input="FIRST_NAME",
        expected="FIRST_NAME",
        case="upper_snake",
    ),
    # ==========================================
    # upper
    # ==========================================
    Case(
        input="First Name",
        expected="FIRSTNAME",
        case="upper",
    ),
    Case(
        input="FIRST NAME",
        expected="FIRSTNAME",
        case="upper",
    ),
    # ==========================================
    # lower
    # ==========================================
    Case(
        input="First Name",
        expected="firstname",
        case="lower",
    ),
    Case(
        input="first name",
        expected="firstname",
        case="lower",
    ),
    # ==========================================
    # pascal
    # ==========================================
    Case(
        input="First Name",
        expected="FirstName",
        case="pascal",
    ),
    Case(
        input="FirstName",
        expected="FirstName",
        case="pascal",
    ),
    # ==========================================
    # camel
    # ==========================================
    Case(
        input="First Name",
        expected="firstName",
        case="camel",
    ),
    Case(
        input="firstName",
        expected="firstName",
        case="camel",
    ),
    # ==========================================
    # kebab
    # ==========================================
    Case(
        input="First Name",
        expected="first-name",
        case="kebab",
    ),
    Case(
        input="first-name",
        expected="first-name",
        case="kebab",
    ),
    # ==========================================
    # train
    # ==========================================
    Case(
        input="First Name",
        expected="First-Name",
        case="train",
    ),
    Case(
        input="First-Name",
        expected="First-Name",
        case="train",
    ),
    # ==========================================
    # cobol
    # ==========================================
    Case(
        input="First Name",
        expected="FIRST-NAME",
        case="cobol",
    ),
    Case(
        input="FIRST-NAME",
        expected="FIRST-NAME",
        case="cobol",
    ),
]


def test_col_renamer():

    for case in test_cases:
        renamer = ColRenamer(case=case.case)
        result = renamer.rename(case.input)

        assert result == case.expected, (
            f"Failed for case: {case.case}, input: {case.input}, expected: {case.expected}, got: {result}"
        )
