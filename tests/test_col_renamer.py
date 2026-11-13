"""Tests for ColRenamer: renaming column names into each supported case style."""

from dataclasses import dataclass

from dataclean import ColRenamer


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
    """This walks through every supported naming style, such as snake, camel, kebab and
    pascal. A spaced name like First Name is converted into each style, and a name
    already in that style comes back unchanged."""
    for case in test_cases:
        renamer = ColRenamer(case=case.case)
        result = renamer.rename(case.input)

        assert result == case.expected, (
            f"Failed for case: {case.case}, input: {case.input}, expected: {case.expected}, got: {result}"
        )


# ==========================================
# cleaning, prefixing, dedupe, length
# ==========================================
def test_default_case_is_snake() -> None:
    assert ColRenamer().case == "snake"


def test_cleans_invisible_emoji_accents_and_specials() -> None:
    renamer = ColRenamer()
    assert renamer.rename("﻿First​ Name") == "first_name"
    assert renamer.rename("Phone \U0001f4de") == "phone"
    assert renamer.rename("Café Name") == "cafe_name"
    assert renamer.rename("Amount (%) #1") == "amount_1"


def test_digit_leading_and_empty_names_get_prefix() -> None:
    renamer = ColRenamer()
    assert renamer.rename("2nd phone").startswith("col_")
    assert renamer.rename("###") == "col"


def test_rename_cols_dedupes_collisions() -> None:
    renamer = ColRenamer()
    assert renamer.rename_cols(["Phone", "phone", "PHONE"]) == {
        "Phone": "phone_2",
        "PHONE": "phone_3",
    }


def test_rename_cols_dedupes_against_untouched_names() -> None:
    assert ColRenamer().rename_cols(["Phone", "phone"]) == {"Phone": "phone_2"}


def test_max_length_keeps_dedupe_suffix() -> None:
    renamer = ColRenamer(max_length=6)
    result = renamer.rename_cols(["customer_name", "Customer Name"])
    assert all(len(v) <= 6 for v in result.values())
    assert len(set(result.values())) == len(result)


def test_aliases_fix_abbreviations_and_compounds() -> None:
    renamer = ColRenamer()
    assert renamer.rename("fname") == "first_name"
    assert renamer.rename("lname_2") == "last_name_2"
    assert renamer.rename("FName") == "first_name"
    assert renamer.rename("mname") == "middle_name"
    assert renamer.rename("lnamefname_3") == "last_name_first_name_3"
    assert renamer.rename("rowguid") == "row_guid"
    assert renamer.rename("dateofbirth") == "date_of_birth"
    assert renamer.rename("postcode") == "post_code"
    assert renamer.rename("filename") == "file_name"
    assert renamer.rename("username") == "user_name"


def test_custom_aliases_replace_defaults() -> None:
    assert ColRenamer(aliases={}).rename("rowguid") == "row_gui_d"
    assert ColRenamer(aliases={"cust": ("customer",)}).rename("cust id") == (
        "customer_id"
    )
