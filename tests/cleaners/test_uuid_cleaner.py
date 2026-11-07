import pytest

from dataclean import UuidCleaner

# ------------------------------------------------------------------------------
# CORE PROPERTIES & SCHEMA VERIFICATION
# ------------------------------------------------------------------------------


def test_uuid_cleaner_metadata():
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
    cleaner = UuidCleaner(out_format=out_fmt)
    assert cleaner.clean_row(input_val) == expected_output


def test_uuid_clean_value_invalid_returns_none():
    cleaner = UuidCleaner()
    # Malformed strings or shortened sequences fail validation safely
    assert cleaner.clean_row("short-uuid-123") is None
    assert cleaner.clean_row("123e4567-e89b-12d3-a456-42661417400Z") is None


# ------------------------------------------------------------------------------
# VERSION GUARDRAIL TESTS
# ------------------------------------------------------------------------------


def test_uuid_version_enforcement():
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
    assert UuidCleaner().clean_row(value) is None


def test_uuid_allow_nil_and_allow_max_flags_are_independent():
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
    assert UuidCleaner().clean_row(value) == GOOD


@pytest.mark.parametrize(
    "value",
    [
        "deadbeef deadbeef deadbeef deadbeef",
        "3f2504e04f89-11d3-9a0c0305e82c3304",
        "3f2504e0-4f89_11d3-9a0c-0305e82c3304",
        "3f2504e0-4f89-11d3-9a0c-0305e82c330",
        "3f2504e0-4f89-11d3-9a0c-0305e82c33045",
        "id: " + GOOD,
        GOOD + ", extra",
        "no. " + GOOD,
    ],
)
def test_uuid_rejects_other_shapes_and_embedded_text_by_default(value):
    assert UuidCleaner().clean_row(value) is None


@pytest.mark.parametrize(
    "value",
    ["id: " + GOOD, GOOD + ", extra", "no. " + GOOD, "ref=" + GOOD.upper() + "."],
)
def test_uuid_extract_from_text_pulls_one_uuid(value):
    assert UuidCleaner(extract_from_text=True).clean_row(value) == GOOD


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
    assert UuidCleaner(extract_from_text=True).clean_row(value) is None
