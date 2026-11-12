"""Cleaner that recognizes personal-name columns, fixes their casing and nulls placeholders."""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, override

from cleanco import basename

from dataclean.engine import DataFrame, DataType
from dataclean.types import checked
from dataclean.utils import (
    TEXT_NULL_TOKENS,
    is_null_token,
    looks_like_code,
    looks_like_link,
    looks_like_path,
    null_token_set,
    remove_emoji,
    remove_invisible,
    replace_control_chars,
    strip_html,
    title_case,
)

from .cleaner import Cleaner

# A digit or "&" shows a company ("3M", "AT&T"), so its casing is left alone.
# Code, emails and URLs never get this far: they are nulled as junk first.
_COMPANY_MARK = re.compile(r"[\d&]")

# Legal suffixes written one way. Decision: "Limited" and "Ltd." both become
# "LTD", and the rest of the company name keeps the writer's casing. Matching
# ignores dots and case, so "p.l.c." and "Pvt." are found too. Decision: the
# word "Company" is left as written, since it is also an ordinary name word
# ("McKinsey & Company").
_COMPANY_SUFFIXES = {
    "limited": "LTD",
    "ltd": "LTD",
    "incorporated": "INC",
    "inc": "INC",
    "corporation": "CORP",
    "corp": "CORP",
    "co": "CO",
    "private": "PVT",
    "pvt": "PVT",
    "llc": "LLC",
    "llp": "LLP",
    "plc": "PLC",
    "gmbh": "GMBH",
}

# Words that stay lower case inside a name, as in "Ludwig van Beethoven".
_PARTICLES = frozenset(
    "al bin bint da de del della den der di du el ibn la le ten ter van von".split()
)
_ROMAN_SUFFIXES = frozenset({"ii", "iii", "iv"})

# Shortest legal-suffix text (letters only) that still counts as a company.
# Two-letter suffixes such as "Sa" or "Se" are also common surname endings.
_MIN_SUFFIX_LETTERS = 3


def _has_company_suffix(value: str) -> bool:
    """Whether ``value`` ends in a legal suffix such as "Ltd", "LLP" or "GmbH".

    Decision: a suffix of fewer than three letters, such as "Sa", "Se" or "Co",
    does not count unless it has a dot or "&", because those are also common
    surname endings ("Mary Sa") and a wrong company guess would skip casing
    or rewrite a person's name.
    """
    base = basename(value)
    if base == value or not value.startswith(base):
        return base != value
    suffix = value[len(base) :]
    return (
        sum(ch.isalpha() for ch in suffix) >= _MIN_SUFFIX_LETTERS
        or "." in suffix
        or "&" in suffix
    )


def _standardize_company_suffix(value: str) -> str:
    """Write the legal suffix at the end of a company name in one standard form.

    "Reliance Industries Pvt. Ltd." becomes "Reliance Industries PVT LTD". Only
    called for a value that has a company suffix, so a person named "Wei Co"
    is not changed (see ``_has_company_suffix``).
    """
    words = value.split(" ")
    for i in range(len(words) - 1, 0, -1):
        standard = _COMPANY_SUFFIXES.get(words[i].replace(".", "").strip(",").lower())
        if standard is None:
            break
        words[i] = standard
    return " ".join(words)


def _is_acronym(word: str) -> bool:
    """Whether an upper-case ``word`` reads as an acronym, such as "IBM" or "KPMG".

    Short words and words without a vowel count, since "JOHN" cannot be told
    from "HBOS" but "IBM" and "KPMG" are far more likely acronyms. Only a
    single word is judged this way: "JAN VAN DER BERG" is clearly a person.
    """
    letters = unicodedata.normalize("NFKD", word).casefold()
    return len(word) <= _MAX_ACRONYM_LETTERS or not any(
        ch in "aeiouy" for ch in letters
    )


_MAX_ACRONYM_LETTERS = 3


def _fix_case(value: str) -> str:
    """Title-case a name written all lower or all upper case.

    A value with mixed case, such as "McDonald", is left alone since the
    writer most likely chose that casing. So is a value that looks like a
    company or like something other than a name.
    """
    upper = value == value.upper()
    if value != value.lower() and not upper:
        return value
    if _COMPANY_MARK.search(value) or _has_company_suffix(value):
        return value
    if " " not in value and upper and _is_acronym(value):
        return value
    return title_case(value, small_words=_PARTICLES, upper_last_words=_ROMAN_SUFFIXES)


@checked
@dataclass
class NameCleaner(Cleaner):
    """Cleans person and company names in name columns.

    It claims person-name columns (``fname``, ``lname``, ``mname``,
    ``first_name``, ``surname``, ``full_name``, ...) so that no other cleaner
    does. CRMs keep private and company clients in the same columns, so every
    rule below has to leave companies alone. Values still get the pipeline's
    input normalization like any other cleaner (surrounding whitespace is
    stripped, blank strings become null).

    Rules, in order, with the reason for each:

    1. HTML tags, invisible and direction characters and control characters
       are removed, and Unicode is normalised with NFKC, so full-width letters
       (``ＴＨＥ``) and combining accents become plain, comparable text.
    2. A placeholder (``null_tokens``) becomes null.
    3. A value with no letters (``123``, ``0``, ``''``) becomes null: it cannot
       be a name.
    4. A value longer than ``max_length`` becomes null: real names stay well
       under it, so a longer value is pasted text or junk.
    5. A value that looks like code, a template, SQL, a character repeated
       many times (``looks_like_code``), a file path or path traversal
       (``looks_like_path``), or an email or URL (``looks_like_link``)
       becomes null: it is never a name, and keeping it would let injection
       strings through. These checks belong to this cleaner, not to the
       helpers: a path or email is valid in a file-path or email column.
    6. A company's legal suffix is written one way (``Limited``, ``Ltd.`` ->
       ``LTD``; ``Incorporated`` -> ``INC``). Only a clear suffix counts, see
       ``_has_company_suffix``.
    7. A value written all lower or all upper case is title-cased (``john``,
       ``JOHN`` -> ``John``), with ``Mc`` names, lower-case particles
       (``van``, ``de``) and roman-numeral suffixes handled. Mixed case such
       as ``McDonald`` is kept, since the writer chose it. Companies (a legal
       suffix, a digit or ``&``) and acronyms are kept as typed.

    Accepted limits: a single all-upper word of three letters or fewer, or
    without a vowel, is read as an acronym (``IBM``, ``KPMG``), so a lone
    ``AMY`` stays as typed. Other acronyms such as ``HBOS`` cannot be told from
    a name and become ``Hbos``. A value that is all lower case but is not a name
    (``tab here``) is title-cased too, since nothing can tell it apart.

    Only string columns are matched, and a bare ``name`` column is not
    (it is often a company or product name).

    Attributes:
        null_tokens: Placeholder values (compared case-insensitively) that
            become null. ``na`` and ``nan`` are left out of the default, since
            they are real names (``Nan``); the exact string ``NaN`` is kept
            too, by decision.
        null_if_no_letters: Whether a value with no letters becomes null.
        max_length: Longest value kept; a longer one becomes null. None turns
            the limit off.
        null_junk: Whether a value that looks like code, a path, an email, a
            URL or a repeated character becomes null.
        standardize_company_suffix: Whether a legal suffix such as ``Limited``
            is written as ``LTD``.
        fix_case: Whether a value written all lower or all upper case is
            title-cased.
    """

    null_tokens: tuple[str, ...] = TEXT_NULL_TOKENS
    null_if_no_letters: bool = True
    max_length: int | None = 150
    null_junk: bool = True
    standardize_company_suffix: bool = True
    fix_case: bool = True

    # Short forms must stand alone (or be concatenated, e.g. "lnamefname") so
    # that "colname" or "filename" never match.
    _SHORT_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:^|[^a-z])(?:[flm]name)+(?:$|[^a-z])"
    )
    _LONG_NAME_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"first_?name|last_?name|middle_?name|full_?name|given_?name|"
        r"family_?name|maiden_?name|forename|surname"
    )

    _null_set: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Initialize base cleaner state and build the placeholder lookup."""
        super().__post_init__()
        self._null_set = null_token_set(self.null_tokens)

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Return ``v`` cleaned by the rules in the class docstring, or None.

        Args:
            v: The name value (already stripped and non-blank).

        Returns:
            The cleaned name, or None if nothing is left, it is a placeholder,
            it has no letters, or it looks like junk (each when enabled).
        """
        cleaned = replace_control_chars(remove_invisible(remove_emoji(strip_html(v))))
        cleaned = " ".join(unicodedata.normalize("NFKC", cleaned).split())
        v = cleaned
        if is_null_token(v, self._null_set):
            return None
        if self.null_if_no_letters and not any(ch.isalpha() for ch in v):
            return None
        if self.max_length is not None and len(v) > self.max_length:
            return None
        if self.null_junk and (
            looks_like_code(v) or looks_like_path(v) or looks_like_link(v)
        ):
            return None
        if self.standardize_company_suffix and _has_company_suffix(v):
            v = _standardize_company_suffix(v)
        return _fix_case(v) if self.fix_case else v

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence from the column name looking like a person's name.

        Args:
            df: The dataframe being inspected; used only to skip columns that
                are known not to be strings.
            cols: Candidate column name(s); only the first is considered.

        Returns:
            1.0 if the column is a string (or unknown-typed) column whose
            name is a person-name column, otherwise 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0

        column = cols_tuple[0]
        if dict(df.cols()).get(column) not in (None, DataType.STR):
            return 0.0

        name = column.lower()
        if self._SHORT_NAME_RE.search(name) or self._LONG_NAME_RE.search(name):
            return 1.0

        return 0.0
