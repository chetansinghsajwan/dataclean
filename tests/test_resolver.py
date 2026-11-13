"""Tests for column-to-cleaner resolution in Resolver."""

import pandas as pd
from dataclean_pandas import PandasDataFrame

from dataclean import Cleaner, EmailCleaner, NameCleaner
from dataclean.engine import DataFrame
from dataclean.pipeline.cleaner_resolver import Resolver


def _df(*cols: str) -> DataFrame:
    return PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))


class ByName(Cleaner):
    """Single-input cleaner scoring columns from a name -> score table."""

    SCORES: dict[str, float] = {}

    def clean_row(self, value: str | None) -> str | None:
        return value

    def match_score(
        self, df: DataFrame, cols: tuple[str, ...], words: tuple[str, ...]
    ) -> float:
        return self.SCORES.get(cols[0], 0.0)


def _by_name(**scores: float) -> ByName:
    return type("Scored", (ByName,), {"SCORES": scores})()


class Pair(Cleaner):
    """Two required inputs, matched by role name hints in column names."""

    def clean_row(self, first: str | None, second: str | None) -> str | None:
        return first


class PairOptionalSecond(Cleaner):
    def clean_row(self, first: str | None, second: str | None = None) -> str | None:
        return first


def test_explicit_mapping_wins_with_full_confidence() -> None:
    """If the user names a cleaner for a column, that choice beats whatever auto-
    detection would pick. They know their data better than a guess does, so it is
    recorded with full confidence."""
    explicit = _by_name()
    auto = _by_name(a=0.9)
    assignments = Resolver(cleaners=(auto,)).resolve(
        _df("a", "b"), {"a", "b"}, {"a": explicit}
    )

    assert len(assignments) == 1
    assert assignments[0].cleaner is explicit
    assert assignments[0].confidence == 1.0


def test_explicit_mapping_for_unknown_or_ignored_column_is_skipped() -> None:
    """A mapping for a column that doesn't exist or is being ignored has nothing to act
    on. We skip it quietly instead of raising an error."""
    assignments = Resolver(cleaners=()).resolve(
        _df("a"), {"a"}, {"missing": _by_name()}
    )
    assert assignments == ()


def test_score_threshold_is_inclusive_at_half() -> None:
    """A cleaner needs a score of at least 0.5 to claim a column. A column scoring
    exactly 0.5 is in and 0.49 is out, which makes the cut-off easy to predict."""
    cleaner = _by_name(keep=0.5, drop=0.49)
    assignments = Resolver(cleaners=(cleaner,)).resolve(
        _df("keep", "drop"), {"keep", "drop"}
    )
    assert [a.role_columns["value"] for a in assignments] == ["keep"]


def test_single_input_cleaner_claims_every_matching_column() -> None:
    """A cleaner that takes one column can be useful on many. It claims every column
    that scores well and skips the weak one."""
    cleaner = _by_name(a=0.8, b=0.9, c=0.1)
    assignments = Resolver(cleaners=(cleaner,)).resolve(
        _df("a", "b", "c"), {"a", "b", "c"}
    )
    assert {a.role_columns["value"] for a in assignments} == {"a", "b"}


def test_columns_are_claimed_once() -> None:
    """Two cleaners both want the same column, but it should only be cleaned by one of
    them. When they are equally suited, the one registered first wins."""
    first, second = _by_name(a=0.8), _by_name(a=0.9)
    assignments = Resolver(cleaners=(first, second)).resolve(_df("a"), {"a"})
    # Registration order wins for equally constrained cleaners.
    assert len(assignments) == 1
    assert assignments[0].cleaner is first


def test_multi_input_cleaner_gets_first_pick() -> None:
    """A cleaner that needs several columns is the more specific match. So it chooses
    first, and the single-column cleaner doesn't steal one of its columns."""
    single = _by_name(first_col=0.9)
    pair = Pair()
    assignments = Resolver(cleaners=(single, pair)).resolve(
        _df("first_col", "second_col"), {"first_col", "second_col"}
    )

    assert [a.cleaner for a in assignments] == [pair]
    assert dict(assignments[0].role_columns) == {
        "first": "first_col",
        "second": "second_col",
    }


def test_multi_input_cleaner_skipped_when_required_role_unmatched() -> None:
    """A cleaner needing two columns can't run if only one exists. Instead of failing,
    it is simply not used."""
    assignments = Resolver(cleaners=(Pair(),)).resolve(_df("first_col"), {"first_col"})
    assert assignments == ()


def test_optional_role_left_unfilled() -> None:
    """When a cleaner has an optional second input and no column fits it, the cleaner
    should still run with just the first. Optional means it can do without."""
    assignments = Resolver(cleaners=(PairOptionalSecond(),)).resolve(
        _df("first_col"), {"first_col"}
    )
    assert len(assignments) == 1
    assert dict(assignments[0].role_columns) == {"first": "first_col"}


def test_scoring_errors_count_as_no_match() -> None:
    """If a cleaner crashes while scoring a column, we treat it as saying no. One badly
    behaved cleaner shouldn't be able to bring down the whole resolution."""

    class Broken(ByName):
        def match_score(
            self, df: DataFrame, cols: tuple[str, ...], words: tuple[str, ...]
        ) -> float:
            raise ValueError("boom")

    assert Resolver(cleaners=(Broken(),)).resolve(_df("a"), {"a"}) == ()


class PrimaryWithContext(Cleaner):
    """Primary-led cleaner with an extra optional (context) role, like PhoneCleaner."""

    def clean_row(self, value: str | None, country: str | None = None) -> str | None:
        return value

    def match_score(
        self, df: DataFrame, cols: tuple[str, ...], words: tuple[str, ...]
    ) -> float:
        return 1.0 if cols[0].startswith("ph") else 0.0


def test_primary_led_cleaner_with_context_role_claims_every_matching_column() -> None:
    """Some cleaners, like the phone one, have a main column plus an optional context
    column such as country. Every column matching the main role is claimed, and the
    context role is left unfilled at this stage."""
    assignments = Resolver(cleaners=(PrimaryWithContext(),)).resolve(
        _df("ph_a", "ph_b", "other"), {"ph_a", "ph_b", "other"}
    )

    assert {a.role_columns["value"] for a in assignments} == {"ph_a", "ph_b"}
    assert all(set(a.role_columns) == {"value"} for a in assignments)


def test_phone_cleaner_claims_tel_mobile_and_fax() -> None:
    """With a realistic set of column names, the phone cleaner picks up tel, mobile and
    fax. It ignores email_note, which merely sounds like it could be related."""
    from dataclean import PhoneCleaner

    cols = {"tel", "mobile", "fax", "email_note"}
    assignments = Resolver(cleaners=(PhoneCleaner(),)).resolve(_df(*cols), cols)

    assert {a.role_columns["value"] for a in assignments} == {"tel", "mobile", "fax"}


def test_address_cleaner_matches_numbered_address_columns() -> None:
    """Plenty of tables name their columns address1, address2, address3, town, county
    and so on. The address cleaner should map them to the right line roles and treat
    the whole set as one address, without pulling in country."""
    from dataclean import AddressCleaner

    cols = {
        "address1",
        "address2",
        "address3",
        "town",
        "county",
        "postcode",
        "country",
    }
    assignments = Resolver(cleaners=(AddressCleaner(),)).resolve(_df(*cols), cols)

    assert len(assignments) == 1
    assert dict(assignments[0].role_columns) == {
        "address_line1": "address1",
        "address_line2": "address2",
        "address_line3": "address3",
        "town": "town",
        "county": "county",
        "postcode": "postcode",
    }


def test_address_cleaner_still_matches_address_line_names() -> None:
    """The older address_line1 style names, plus a plain zip column, should keep
    working. Zip is understood as the postcode."""
    from dataclean import AddressCleaner

    cols = {"address_line1", "address_line2", "zip"}
    assignments = Resolver(cleaners=(AddressCleaner(),)).resolve(_df(*cols), cols)

    assert dict(assignments[0].role_columns) == {
        "address_line1": "address_line1",
        "address_line2": "address_line2",
        "postcode": "zip",
    }


def test_address_cleaner_matches_without_a_first_line_column() -> None:
    """Not every table has full street lines. A table with just county and postcode is
    still an address, so it is matched anyway."""
    from dataclean import AddressCleaner

    cols = {"county", "postcode"}
    assignments = Resolver(cleaners=(AddressCleaner(),)).resolve(_df(*cols), cols)

    assert dict(assignments[0].role_columns) == {
        "county": "county",
        "postcode": "postcode",
    }


def test_resolver_matches_on_words_of_the_raw_column_name() -> None:
    """Names are matched on their split words, with no renaming step, so
    spaces, ``fname`` and ``E-Mail`` all reach the cleaners they should."""
    cols = {"First Name", "fname", "E-Mail", "hotel"}
    df = PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))

    assignments = Resolver(cleaners=(NameCleaner(), EmailCleaner())).resolve(df, cols)

    claimed = {(type(a.cleaner).__name__, a.role_columns["value"]) for a in assignments}
    assert claimed == {
        ("NameCleaner", "First Name"),
        ("NameCleaner", "fname"),
        ("EmailCleaner", "E-Mail"),
    }
