"""Tests for column-to-cleaner resolution in Resolver."""

import pandas as pd
from dataclean_pandas import PandasDataFrame

from dataclean import Cleaner
from dataclean.engine import DataFrame
from dataclean.pipeline.cleaner_resolver import Resolver


def _df(*cols: str) -> DataFrame:
    return PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))


class ByName(Cleaner):
    """Single-input cleaner scoring columns from a name -> score table."""

    SCORES: dict[str, float] = {}

    def clean_row(self, value: str | None) -> str | None:
        return value

    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
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
    explicit = _by_name()
    auto = _by_name(a=0.9)
    assignments = Resolver(cleaners=(auto,)).resolve(
        _df("a", "b"), {"a", "b"}, {"a": explicit}
    )

    assert len(assignments) == 1
    assert assignments[0].cleaner is explicit
    assert assignments[0].confidence == 1.0


def test_explicit_mapping_for_unknown_or_ignored_column_is_skipped() -> None:
    assignments = Resolver(cleaners=()).resolve(
        _df("a"), {"a"}, {"missing": _by_name()}
    )
    assert assignments == ()


def test_score_threshold_is_inclusive_at_half() -> None:
    cleaner = _by_name(keep=0.5, drop=0.49)
    assignments = Resolver(cleaners=(cleaner,)).resolve(
        _df("keep", "drop"), {"keep", "drop"}
    )
    assert [a.role_columns["value"] for a in assignments] == ["keep"]


def test_single_input_cleaner_claims_every_matching_column() -> None:
    cleaner = _by_name(a=0.8, b=0.9, c=0.1)
    assignments = Resolver(cleaners=(cleaner,)).resolve(
        _df("a", "b", "c"), {"a", "b", "c"}
    )
    assert {a.role_columns["value"] for a in assignments} == {"a", "b"}


def test_columns_are_claimed_once() -> None:
    first, second = _by_name(a=0.8), _by_name(a=0.9)
    assignments = Resolver(cleaners=(first, second)).resolve(_df("a"), {"a"})
    # Registration order wins for equally constrained cleaners.
    assert len(assignments) == 1
    assert assignments[0].cleaner is first


def test_multi_input_cleaner_gets_first_pick() -> None:
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
    assignments = Resolver(cleaners=(Pair(),)).resolve(_df("first_col"), {"first_col"})
    assert assignments == ()


def test_optional_role_left_unfilled() -> None:
    assignments = Resolver(cleaners=(PairOptionalSecond(),)).resolve(
        _df("first_col"), {"first_col"}
    )
    assert len(assignments) == 1
    assert dict(assignments[0].role_columns) == {"first": "first_col"}


def test_scoring_errors_count_as_no_match() -> None:
    class Broken(ByName):
        def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
            raise ValueError("boom")

    assert Resolver(cleaners=(Broken(),)).resolve(_df("a"), {"a"}) == ()
