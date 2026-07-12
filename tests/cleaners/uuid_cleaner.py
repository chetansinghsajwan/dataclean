import pytest

from dataclean.cleaners.uuid_cleaner import UuidCleaner

# ------------------------------------------------------------------------------
# CORE PROPERTIES & SCHEMA VERIFICATION
# ------------------------------------------------------------------------------


def test_uuid_cleaner_metadata():
    cleaner = UuidCleaner()
    assert cleaner.name() == "UuidCleaner"
    assert cleaner.output_schema() == "str"


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
    assert cleaner.clean_value(input_val) == expected_output


def test_uuid_clean_value_invalid_returns_none():
    cleaner = UuidCleaner()
    # Malformed strings or shortened sequences fail validation safely
    assert cleaner.clean_value("short-uuid-123") is None
    assert cleaner.clean_value("123e4567-e89b-12d3-a456-42661417400Z") is None


# ------------------------------------------------------------------------------
# VERSION GUARDRAIL TESTS
# ------------------------------------------------------------------------------


def test_uuid_version_enforcement():
    # A structurally valid v4 UUID string (exactly 32 hex characters excl. hyphens)
    v4_uuid = "9f8e7d6c-5b4a-4321-a987-6543210fedcb"

    # Allow only v7 time-ordered identifiers -> returns None because version is 4
    v7_only_cleaner = UuidCleaner(allowed_versions={7})
    assert v7_only_cleaner.clean_value(v4_uuid) is None

    # Allow any valid version configuration -> passes seamlessly now
    lax_cleaner = UuidCleaner(allowed_versions=None)
    assert lax_cleaner.clean_value(v4_uuid) is not None
