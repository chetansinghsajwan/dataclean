import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import AddressCleaner, CountryCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver

# Output tuple positions of AddressCleaner.clean_row.
STATE, POSTCODE, LINE, STREET, HOUSE_NO, TOWN, LINE2, LINE3 = range(8)


def _clean(**kwargs: str | None) -> tuple[str | None, ...]:
    result = AddressCleaner().clean_row(**kwargs)
    assert result is not None
    return result


def _df(**columns: list[str]) -> PandasDataFrame:
    return PandasDataFrame(df=pd.DataFrame(columns))


# ==============================================================================
# 1. SCHEMA
# ==============================================================================


def test_address_cleaner_has_no_country_role() -> None:
    cleaner = AddressCleaner()

    assert "country" not in {col.key for col in cleaner.inputs.cols}
    assert all("country" not in col.roles for col in cleaner.outputs.cols)


def test_address_cleaner_has_no_required_input() -> None:
    assert not any(col.required for col in AddressCleaner().inputs.cols)


# ==============================================================================
# 2. TOWN AND COUNTY
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("london", "London"),
        ("MANCHESTER", "Manchester"),
        ("  leeds   upon  tyne ", "Leeds Upon Tyne"),
        ("stoke-on-trent", "Stoke-On-Trent"),
        ("king's lynn", "King's Lynn"),
        ("McDonald Heights", "McDonald Heights"),
        ("Greater London", "Greater London"),
    ],
)
def test_address_cleaner_title_cases_town_only_when_uniform_case(
    raw: str, expected: str
) -> None:
    assert _clean(address_line1="1 High Street", town=raw)[TOWN] == expected


@pytest.mark.parametrize(
    "raw", ["%s%s%s%n", "<script>alert(1)</script>", "{{7*7}}", "../../etc/passwd"]
)
def test_address_cleaner_leaves_town_that_is_not_a_place_name_as_is(raw: str) -> None:
    assert _clean(address_line1="1 High Street", town=raw)[TOWN] == raw


def test_address_cleaner_cleans_county_into_state() -> None:
    assert _clean(address_line1="1 High Street", county="kent")[STATE] == "Kent"


def test_address_cleaner_keeps_missing_town_and_county_as_none() -> None:
    result = _clean(address_line1="1 High Street")

    assert result[TOWN] is None
    assert result[STATE] is None


# ==============================================================================
# 3. POSTCODE
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("sw1a1aa", "SW1A 1AA"),
        ("SW1A 1AA", "SW1A 1AA"),
        ("sw1a   1aa", "SW1A 1AA"),
        ("m11ae", "M1 1AE"),
        ("EC1A-1BB", "EC1A 1BB"),
        ("12345-6789", "123456789"),
        ("ncr-110001", "NCR110001"),
        ("110001", "110001"),
    ],
)
def test_address_cleaner_normalizes_postcode_and_spaces_uk_ones(
    raw: str, expected: str
) -> None:
    assert _clean(address_line1="1 High Street", postcode=raw)[POSTCODE] == expected


@pytest.mark.parametrize("raw", ["???", "---", "- -"])
def test_address_cleaner_nulls_postcode_without_letters_or_digits(raw: str) -> None:
    assert _clean(address_line1="1 High Street", postcode=raw)[POSTCODE] is None


# ==============================================================================
# 4. ADDRESS LINES
# ==============================================================================


def test_address_cleaner_collapses_whitespace_in_every_line() -> None:
    result = _clean(
        address_line1="12   baker  street",
        address_line2="2nd   floor",
        address_line3="Westminster  ",
    )

    assert result[LINE] == "12 baker street"
    assert result[LINE2] == "2nd floor"
    assert result[LINE3] == "Westminster"


def test_address_cleaner_splits_a_leading_house_number() -> None:
    result = _clean(address_line1="12 baker street")

    assert result[STREET] == "baker street"
    assert result[HOUSE_NO] == "12"


def test_address_cleaner_keeps_whole_line_as_street_without_a_number() -> None:
    result = _clean(address_line1="PO Box 99")

    assert result[STREET] == "PO Box 99"
    assert result[HOUSE_NO] is None


# ==============================================================================
# 5. DETECTION
# ==============================================================================


def test_address_cleaner_claims_town_address3_and_postcode_by_role() -> None:
    cols = {"address1", "address2", "address3", "town", "county", "postcode"}
    assignments = Resolver(cleaners=(AddressCleaner(),)).resolve(
        _df(**{col: ["v"] for col in cols}), cols
    )

    assert dict(assignments[0].role_columns) == {
        "address_line1": "address1",
        "address_line2": "address2",
        "address_line3": "address3",
        "town": "town",
        "county": "county",
        "postcode": "postcode",
    }


def test_country_columns_go_to_country_cleaner_not_address_cleaner() -> None:
    cols = {"address1", "country", "_client_country_of_incorporation"}
    assignments = Resolver(cleaners=(AddressCleaner(), CountryCleaner())).resolve(
        _df(**{col: ["v"] for col in cols}), cols
    )

    by_cleaner = {a.cleaner.name: set(a.role_columns.values()) for a in assignments}
    assert by_cleaner["AddressCleaner"] == {"address1"}
    country_columns = {
        a.role_columns["value"]
        for a in assignments
        if a.cleaner.name == "CountryCleaner"
    }
    assert country_columns == {"country", "_client_country_of_incorporation"}


# ==============================================================================
# 6. PIPELINE
# ==============================================================================


def test_missing_optional_columns_do_not_shift_values_between_roles() -> None:
    # No town, county or address2/3 columns: the postcode must still reach the
    # postcode role, not whichever role comes next in the schema.
    cleaned = Pipeline(cleaners=(AddressCleaner(),)).fit_transform(
        _df(address1=["12 High Street"], postcode=["br1 1aa"])
    )

    assert cleaned.df is not None
    row = cleaned.df.iloc[0]
    assert row["address1_postcode_cleaned"] == "BR1 1AA"
    assert row["address1_street_cleaned"] == "High Street"
    assert row["address1_house_no_cleaned"] == "12"
    assert row["address1_state_cleaned"] is None
    assert row["address1_town_cleaned"] is None


def test_country_is_cleaned_in_place_next_to_an_address_group() -> None:
    cleaned = Pipeline(cleaners=(AddressCleaner(), CountryCleaner())).fit_transform(
        _df(
            address1=["", "12 High Street"],
            country=["GBR", "Deutschland"],
            _client_country_of_incorporation=["Malta", "Ireland"],
        )
    )

    assert cleaned.df is not None
    assert cleaned.df["country"].tolist() == ["United Kingdom", "Germany"]
    assert cleaned.df["_client_country_of_incorporation"].tolist() == [
        "Malta",
        "Ireland",
    ]


def test_row_without_a_first_line_still_gets_town_and_postcode() -> None:
    cleaned = Pipeline(cleaners=(AddressCleaner(),)).fit_transform(
        _df(
            address1=["", "1 High Street"],
            town=["london", "leeds"],
            postcode=["???", "ls1 1aa"],
        )
    )

    assert cleaned.df is not None
    assert cleaned.df["address1_town_cleaned"].tolist() == ["London", "Leeds"]
    assert cleaned.df["address1_postcode_cleaned"].tolist() == [None, "LS1 1AA"]


def test_group_without_a_first_line_column_is_named_after_its_first_column() -> None:
    cleaned = Pipeline(cleaners=(AddressCleaner(),)).fit_transform(
        _df(town=["london"], postcode=["sw1a1aa"])
    )

    assert cleaned.df is not None
    assert cleaned.df["town_town_cleaned"].tolist() == ["London"]
    assert cleaned.df["town_postcode_cleaned"].tolist() == ["SW1A 1AA"]
