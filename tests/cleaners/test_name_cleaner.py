"""Tests for NameCleaner: column detection, casing, junk removal and pipeline use."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import ColRenamer, DataFrame, DataType, NameCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver

_words = ColRenamer().words

# ==============================================================================
# 1. METADATA & AUTO-DETECTION
# ==============================================================================


def test_name_cleaner_metadata() -> None:
    """The name cleaner should call itself NameCleaner and produce one string column.
    Other parts of the pipeline depend on that."""
    cleaner = NameCleaner()
    assert cleaner.name == "NameCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


@pytest.mark.parametrize(
    "col_name",
    [
        "fname",
        "lname",
        "mname",
        "FName",
        "lnamefname",
        "first_name",
        "FirstName",
        "last_name",
        "middle_name",
        "surname",
        "forename",
        "full_name",
        "given_name",
        "family_name",
        "client_fname",
    ],
)
def test_name_cleaner_matches_person_name_columns(col_name: str) -> None:
    """All the usual ways of naming a person column, like fname, first_name, surname
    or given_name, should be recognised with full confidence. This lets auto-
    detection hand them to the cleaner."""
    mock_df = MagicMock(spec=DataFrame)
    assert NameCleaner().match_score(mock_df, (col_name,), _words(col_name)) == 1.0


@pytest.mark.parametrize(
    "col_name",
    ["name", "username", "filename", "col_name", "colname", "hostname", "email"],
)
def test_name_cleaner_ignores_non_person_name_columns(col_name: str) -> None:
    """Plain name, username, filename and hostname are not people, even though they
    contain the word name. They score zero so we do not tidy up the wrong data."""
    mock_df = MagicMock(spec=DataFrame)
    assert NameCleaner().match_score(mock_df, (col_name,), _words(col_name)) == 0.0


def test_name_cleaner_ignores_non_string_columns() -> None:
    """Even with a name like first_name, a column of numbers is not a column of
    names. We leave it alone."""
    df = PandasDataFrame(df=pd.DataFrame({"first_name": [1, 2]}))
    assert NameCleaner().match_score(df, ("first_name",), _words("first_name")) == 0.0


def test_name_cleaner_empty_cols_scores_zero() -> None:
    """If there are no columns to look at, the answer is simply zero. No crash and no
    guessing."""
    assert NameCleaner().match_score(MagicMock(spec=DataFrame), (), ()) == 0.0


# ==============================================================================
# 2. CLEANING (pass-through)
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    ["McDonald", "R.P.", "K E", "O'Neil", "Anne-Marie", "van der Berg", "Zoë"],
)
def test_name_cleaner_returns_mixed_case_values_unchanged(raw: str) -> None:
    """Names like McDonald, O'Neil and van der Berg are already written with care.
    When the casing is mixed we trust the writer and leave the value exactly as it
    is."""
    assert NameCleaner().clean_row(raw) == raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("john", "John"),
        ("JOHN", "John"),
        ("john smith", "John Smith"),
        ("brown mary", "Brown Mary"),
        ("O'NEIL", "O'Neil"),
        ("anne-marie", "Anne-Marie"),
        ("NGUYỄN", "Nguyễn"),
        ("mcdonald", "McDonald"),
        ("MCDONALD", "McDonald"),
        ("ludwig van beethoven", "Ludwig van Beethoven"),
        ("JAN VAN DER BERG", "Jan van der Berg"),
        ("john smith iii", "John Smith III"),
        ("vi", "Vi"),
        ("AMY LEE", "Amy Lee"),
        ("RAHUL KUMAR", "Rahul Kumar"),
        ("JOHN", "John"),
    ],
)
def test_name_cleaner_title_cases_uniform_case(raw: str, expected: str) -> None:
    """Names typed all in capitals or all in lower case get fixed up into proper
    capitalisation. Small words like van and suffixes like III keep their usual
    form, and special spellings such as McDonald are restored."""
    assert NameCleaner().clean_row(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["IBM", "KPMG", "BP", "3M", "GM & JW", "AT&T", "KPMG LLP", "marks & spencer"],
)
def test_name_cleaner_leaves_companies_and_acronyms_alone(raw: str) -> None:
    """Things like IBM, KPMG and AT&T are written in capitals on purpose. If we
    title-cased them they would be wrong, so we recognise them and keep them."""
    assert NameCleaner().clean_row(raw) == raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("INFOSYS LIMITED", "INFOSYS LTD"),
        ("Tata Consultancy Services Ltd", "Tata Consultancy Services LTD"),
        ("Reliance Industries Pvt. Ltd.", "Reliance Industries PVT LTD"),
        ("Reliance Industries Private Limited", "Reliance Industries PVT LTD"),
        ("Acme Incorporated", "Acme INC"),
        ("McKinsey & Company", "McKinsey & Company"),
        ("eBay Inc.", "eBay INC"),
        ("Foo Corporation", "Foo CORP"),
        ("Marks & Spencer plc", "Marks & Spencer PLC"),
        ("BP p.l.c.", "BP PLC"),
        ("müller gmbh", "müller GMBH"),
        ("Smith, Jones & Partners llp", "Smith, Jones & Partners LLP"),
    ],
)
def test_name_cleaner_standardizes_company_suffixes(raw: str, expected: str) -> None:
    """The same firm can be written Limited, Ltd or Pvt. Ltd. We write each ending
    one standard way, so the same company lines up across records."""
    assert NameCleaner().clean_row(raw) == expected


def test_name_cleaner_company_suffix_standard_can_be_turned_off() -> None:
    """Some people want company names exactly as written. Turning the option off
    leaves Limited as Limited."""
    cleaner = NameCleaner(standardize_company_suffix=False)
    assert cleaner.clean_row("Acme Limited") == "Acme Limited"


@pytest.mark.parametrize(
    "raw",
    [
        "john@example.com",
        "https://example.com",
        "HTTPS://EXAMPLE.COM",
        "${jndi:ldap://x}",
        "{{config}}",
        "%s%s%s%n",
        "<%= 7*7 %>",
        "select * from users",
        "Robert'); DROP TABLE Students;--",
        "' OR '1'='1",
        "drop table users",
        "../../etc/passwd",
        "/etc/passwd",
        "~/notes",
        "C:\\Windows\\x",
        "union select password",
        "../../etc/passwd" + "=",
    ],
)
def test_name_cleaner_nulls_junk(raw: str) -> None:
    """A name column sometimes holds emails, web links, file paths or attack strings
    like SQL and template tricks. None of these are names, so they become null."""
    assert NameCleaner().clean_row(raw) is None


@pytest.mark.parametrize(
    "raw", ["AT&T", "Select Group", "Dr. Reddy's", "M/s Sharma", "Ac/Dc"]
)
def test_name_cleaner_keeps_names_that_only_resemble_junk(raw: str) -> None:
    """A few real names look suspicious at a glance, such as AT&T, Select Group or
    Ac/Dc. They must get through, because wrongly deleting a real name is worse
    than keeping an odd one."""
    assert NameCleaner().clean_row(raw) == raw


def test_name_cleaner_nulls_filler_and_overlong_values() -> None:
    """Repeated letters and huge strings are filler, not names, so they become null.
    A real name like Aaaron is kept, and you can lift the length limit if you need
    to."""
    assert NameCleaner().clean_row("x" * 300) is None
    assert NameCleaner().clean_row("aaaaaaaa") is None
    assert NameCleaner().clean_row("Aaaron") == "Aaaron"
    assert NameCleaner().clean_row("John " * 40) is None
    assert NameCleaner(max_length=None).clean_row("John " * 40) is not None


def test_name_cleaner_keeps_junk_when_asked() -> None:
    """If you would rather not have junk removed, you can switch it off. An email-
    shaped value then passes through untouched."""
    assert NameCleaner(null_junk=False).clean_row("John@example.com") == (
        "John@example.com"
    )


def test_name_cleaner_normalizes_unicode() -> None:
    """Wide full-width letters and accents typed as two pieces are tidied into their
    normal forms. That way the same name is always stored the same way."""
    assert NameCleaner().clean_row("ＴＨＥ ＱＵＩＣＫ") == "The Quick"
    assert NameCleaner().clean_row("Zoe\u0308") == "Zoë"


@pytest.mark.parametrize("raw", ["mary sa", "kim se", "jo ab"])
def test_name_cleaner_short_suffix_words_do_not_make_a_company(raw: str) -> None:
    """Short endings like sa, se or ab look like company suffixes but also turn up in
    ordinary names. These names are only title-cased, never treated as companies."""
    assert NameCleaner().clean_row(raw) == raw.title()


def test_name_cleaner_removes_text_direction_overrides() -> None:
    """Hidden direction characters can make a name display backwards or hide
    something. We remove them, so Evil is just Evil."""
    assert NameCleaner().clean_row("\u202eEvil\u202c") == "Evil"


def test_name_cleaner_fix_case_can_be_turned_off() -> None:
    """Fixing capitals is optional. With it off, JOHN and john both come back exactly
    as they were typed."""
    cleaner = NameCleaner(fix_case=False)
    assert cleaner.clean_row("JOHN") == "JOHN"
    assert cleaner.clean_row("john") == "john"


@pytest.mark.parametrize("raw", ["123", "0", "''", "{{7*7}}", "1.5", "- -"])
def test_name_cleaner_nulls_values_without_letters(raw: str) -> None:
    """A name needs at least one letter. Numbers, quotes, symbols and dashes on their
    own become null."""
    assert NameCleaner().clean_row(raw) is None


def test_name_cleaner_keeps_values_without_letters_when_asked() -> None:
    """If you do not want the no-letters check, you can turn it off. A value like 123
    is then kept."""
    assert NameCleaner(null_if_no_letters=False).clean_row("123") == "123"


# ==============================================================================
# 3. AUTO-DETECTION END TO END
# ==============================================================================


def test_name_cleaner_is_assigned_by_the_resolver() -> None:
    """In auto-detection the resolver should hand the cleaner only the person-name
    columns. Columns like company and dateofbirth must be left for someone else."""
    cols = {"fname", "lname", "mname", "company", "dateofbirth"}
    df = PandasDataFrame(df=pd.DataFrame({c: ["x"] for c in cols}))

    assignments = Resolver(cleaners=(NameCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {"fname", "lname", "mname"}


def test_name_cleaner_in_the_pipeline_gets_input_normalization_and_placeholders_nulled() -> (
    None
):
    """This runs the cleaner inside a full pipeline on messy data. Extra spaces are
    trimmed, blanks and n/a become null, and only the all-capitals values get re-
    cased."""
    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "fname": ["JOHN", "  mary ", "", None],
                "lname": ["HBOS", "R.P.", "McDonald", "n/a"],
            }
        )
    )

    cleaned = Pipeline(cleaners=(NameCleaner(),)).fit_transform(df)

    result = cleaned.df
    assert result is not None
    fname = result["fname"].tolist()
    lname = result["lname"].tolist()

    # Uniform case is title-cased; whitespace is stripped, blanks and placeholders become null.
    assert fname[:2] == ["John", "Mary"]
    assert pd.isna(fname[2]) and pd.isna(fname[3])
    assert lname[:3] == ["Hbos", "R.P.", "McDonald"]
    assert pd.isna(lname[3])


@pytest.mark.parametrize("raw", ["N/A", "null", "-", "None", "undefined"])
def test_name_cleaner_nulls_placeholders(raw: str) -> None:
    """Values like N/A, null, a dash, None and undefined are how systems say the name
    is missing. We turn them into real nulls."""
    assert NameCleaner().clean_row(raw) is None


@pytest.mark.parametrize("raw", ["Na", "Nan", "Null Singh"])
def test_name_cleaner_keeps_names_that_look_like_placeholders(raw: str) -> None:
    """Na, Nan and Null Singh are real names, or contain one. Only a value that is
    entirely a placeholder is nulled, so these are kept."""
    assert NameCleaner().clean_row(raw) == raw


def test_name_cleaner_null_tokens_can_be_set() -> None:
    """You can set your own list of null words, such as unknown. That list replaces
    the built-in one, so N/A is now kept as it is."""
    assert NameCleaner(null_tokens=("unknown",)).clean_row("Unknown") is None
    assert NameCleaner(null_tokens=("unknown",)).clean_row("N/A") == "N/A"


def test_name_cleaner_strips_html_and_its_scripts() -> None:
    """Names pasted from web pages can come wrapped in tags. We remove the tags and
    any script inside them, a value that is only markup becomes null, and a normal
    name is left alone."""
    cleaner = NameCleaner()
    assert cleaner.clean_row("<b>John</b> Smith<script>x()</script>") == "John Smith"
    assert cleaner.clean_row("<p></p>") is None
    assert cleaner.clean_row("McDonald") == "McDonald"


def test_name_cleaner_removes_invisible_and_control_characters() -> None:
    """Invisible characters and stray tabs or carriage returns sneak into names from
    copy and paste. Invisible ones are removed and the control ones turn into a
    plain space."""
    cleaner = NameCleaner()
    assert cleaner.clean_row("A\u200bb") == "Ab"
    assert cleaner.clean_row("\ufeffBom") == "Bom"
    assert cleaner.clean_row("Tab\there") == "Tab here"
    assert cleaner.clean_row("Cr\rhere") == "Cr here"


def test_name_cleaner_removes_emoji() -> None:
    """People sometimes decorate names with emoji. We drop them, and if nothing but
    emoji was left there is no name at all, so the value becomes null."""
    cleaner = NameCleaner()
    assert cleaner.clean_row("John \U0001f600 Smith") == "John Smith"
    assert cleaner.clean_row("\U0001f680\U0001f680") is None
