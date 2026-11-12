"""Tests for UuidCleaner: formats, version limits, nil/max placeholders and extraction from text."""

import pytest

from dataclean import UuidCleaner

# ------------------------------------------------------------------------------
# CORE PROPERTIES & SCHEMA VERIFICATION
# ------------------------------------------------------------------------------


def test_uuid_cleaner_metadata():
    """The UUID cleaner should produce a single text column, which is what downstream
    steps expect."""
    from dataclean.engine.dataframe import DataType

    cleaner = UuidCleaner()
    assert cleaner.name == "UuidCleaner"
    assert len(cleaner.outputs.cols) == 1
    assert cleaner.outputs.cols[0].dtype == DataType.STR


# ------------------------------------------------------------------------------
# VALUE CLEANING
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_val, out_fmt, expected_output",
    [
        # --- Standard Canonical Layout Variations ---
        (
            "123e4567-e89b-12d3-a456-426614174000",
            UuidCleaner.Format.STANDARD,
            "123e4567-e89b-12d3-a456-426614174000",
        ),
        (
            "123E4567-E89B-12D3-A456-426614174000",
            UuidCleaner.Format.STANDARD,
            "123e4567-e89b-12d3-a456-426614174000",
        ),
        # --- Registry Wrappers and URI Prefixes ---
        (
            "{123e4567-e89b-12d3-a456-426614174000}",
            UuidCleaner.Format.STANDARD,
            "123e4567-e89b-12d3-a456-426614174000",
        ),
        (
            "urn:uuid:123e4567-e89b-12d3-a456-426614174000",
            UuidCleaner.Format.URN,
            "urn:uuid:123e4567-e89b-12d3-a456-426614174000",
        ),
        # --- Corrupted Delimiters & Compact Layouts ---
        (
            "123e4567e89b12d3a456426614174000",
            UuidCleaner.Format.STANDARD,
            "123e4567-e89b-12d3-a456-426614174000",
        ),
        (
            "123e4567.e89b.12d3.a456.426614174000",
            UuidCleaner.Format.COMPACT,
            "123e4567e89b12d3a456426614174000",
        ),
        (
            "'123e4567 e89b 12d3 a456 426614174000'",
            UuidCleaner.Format.COMPACT,
            "123e4567e89b12d3a456426614174000",
        ),
    ],
)
def test_uuid_clean_value_success_matrix(input_val, out_fmt, expected_output):
    """The same UUID turns up in many outfits: upper case, curly braces, a urn prefix,
    no dashes, dots or spaces. They all mean one thing, so each is rewritten into
    whichever format we asked for."""
    cleaner = UuidCleaner(out_format=out_fmt)
    assert cleaner.clean_row(input_val) == expected_output


def test_uuid_clean_value_invalid_returns_none():
    """A short made-up string or one with a non-hex letter like Z can't be a UUID. We
    return null rather than let a bad id through."""
    cleaner = UuidCleaner()
    # Malformed strings or shortened sequences fail validation safely
    assert cleaner.clean_row("short-uuid-123") is None
    assert cleaner.clean_row("123e4567-e89b-12d3-a456-42661417400Z") is None


# ------------------------------------------------------------------------------
# VERSION GUARDRAIL TESTS
# ------------------------------------------------------------------------------


def test_uuid_version_enforcement():
    """You can tell the cleaner to accept only certain UUID versions. A version 4 id is
    turned away when only version 7 is allowed, and accepted when there is no
    restriction."""
    # A structurally valid v4 UUID string (exactly 32 hex characters excl. hyphens)
    v4_uuid = "9f8e7d6c-5b4a-4321-a987-6543210fedcb"

    # Allow only v7 time-ordered identifiers -> returns None because version is 4
    v7_only_cleaner = UuidCleaner(allowed_versions={7})
    assert v7_only_cleaner.clean_row(v4_uuid) is None

    # Allow any valid version configuration -> passes seamlessly now
    lax_cleaner = UuidCleaner(allowed_versions=None)
    assert lax_cleaner.clean_row(v4_uuid) is not None


# ==============================================================================
# NIL AND MAX UUID PLACEHOLDERS
# ==============================================================================

NIL = "00000000-0000-0000-0000-000000000000"
MAX = "ffffffff-ffff-ffff-ffff-ffffffffffff"


@pytest.mark.parametrize("value", [NIL, MAX, "{" + NIL + "}", MAX.upper()])
def test_uuid_nil_and_max_become_none_by_default(value):
    """The all-zero and all-f UUIDs are placeholders rather than real ids. Unless
    someone opts in, we treat them as missing, even when wrapped in braces or
    written in capitals."""
    assert UuidCleaner().clean_row(value) is None


def test_uuid_allow_nil_and_allow_max_flags_are_independent():
    """Allowing the nil UUID should not quietly allow the max one, or the other way
    round. Each placeholder is its own decision."""
    assert UuidCleaner(allow_nil=True).clean_row(NIL) == NIL
    assert UuidCleaner(allow_nil=True).clean_row(MAX) is None
    assert UuidCleaner(allow_max=True).clean_row(MAX) == MAX
    assert UuidCleaner(allow_max=True).clean_row(NIL) is None


# ==============================================================================
# STRICT SHAPES, 0x PREFIX AND TEXT EXTRACTION
# ==============================================================================

GOOD = "3f2504e0-4f89-11d3-9a0c-0305e82c3304"


@pytest.mark.parametrize(
    "value",
    [
        "0x3f2504e04f8911d39a0c0305e82c3304",
        "3f2504e0 4f89 11d3 9a0c 0305e82c3304",
        "3f2504e0_4f89_11d3_9a0c_0305e82c3304",
        "３f2504e0-4f89-11d3-9a0c-0305e82c3304",
    ],
)
def test_uuid_accepts_known_shapes(value):
    """Real data is messy, so a 0x prefix, spaces, underscores or even a full-width
    first digit are all accepted. In every case it is clear which single UUID was
    meant, and we return it in standard form."""
    assert UuidCleaner().clean_row(value) == GOOD


@pytest.mark.parametrize(
    "value",
    [
        "deadbeef deadbeef deadbeef deadbeef",
        "3f2504e04f89-11d3-9a0c0305e82c3304",
        "3f2504e0-4f89_11d3-9a0c-0305e82c3304",
        "3f2504e0-4f89-11d3-9a0c-0305e82c330",
        "3f2504e0-4f89-11d3-9a0c-0305e82c33045",
    ],
)
def test_uuid_rejects_other_shapes(value):
    """Some strings only look a bit like a UUID, such as dashes in the wrong places,
    mixed separators or one digit too many or too few. Guessing here could invent a
    wrong id, so these become null."""
    assert UuidCleaner().clean_row(value) is None


@pytest.mark.parametrize(
    "value",
    ["id: " + GOOD, GOOD + ", extra", "no. " + GOOD, "ref=" + GOOD.upper() + "."],
)
def test_uuid_extract_from_text_pulls_one_uuid(value):
    """Sometimes a UUID sits inside a sentence, like id: followed by the value. When
    exactly one is in there we pull it out, whatever the case or the punctuation
    around it."""
    assert UuidCleaner().clean_row(value) == GOOD


@pytest.mark.parametrize("value", ["id: " + GOOD, GOOD + ", extra"])
def test_uuid_extract_from_text_can_be_turned_off(value):
    """Some users want a cell to be only a UUID and nothing else. With extraction
    switched off, text around the id makes the value null."""
    assert UuidCleaner(extract_from_text=False).clean_row(value) is None


@pytest.mark.parametrize(
    "value",
    [
        GOOD + " and " + GOOD.replace("3304", "3305"),
        "no uuid here",
        "deadbeef deadbeef deadbeef deadbeef",
        "e3f2504e0-4f89-11d3-9a0c-0305e82c3304",
    ],
)
def test_uuid_extract_from_text_rejects_none_or_many(value):
    """If the text has no UUID, or two different ones, there is no single right answer.
    We don't pick for the user, so the result is null."""
    assert UuidCleaner().clean_row(value) is None
