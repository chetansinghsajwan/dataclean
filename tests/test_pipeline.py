"""Tests for Pipeline option handling and execution semantics."""

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import Cleaner, CountryCleaner, EmailCleaner, config
from dataclean.engine import DataFrame
from dataclean.pipeline import Pipeline


def _values(df: DataFrame, col: str) -> list[object]:
    assert df.df is not None
    return list(df.df[col].tolist())


class Upper(Cleaner):
    def clean_row(self, value: str | None) -> str | None:
        assert value is not None
        return value.upper()

    def match_score(self, df: object, cols: tuple[str, ...]) -> float:
        return 0.9 if cols[0].startswith("up") else 0.0


class UpperPerfect(Upper):
    def match_score(self, df: object, cols: tuple[str, ...]) -> float:
        return 1.0 if cols[0].startswith("up") else 0.0


class Shout(Cleaner):
    """Two required inputs; counts calls so tests can see skipped rows."""

    calls: list[tuple[str, str]] = []

    def clean_row(self, first: str, second: str) -> str:
        Shout.calls.append((first, second))
        return f"{first}{second}"


def test_unsupported_dataframe_raises_type_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "dataframe_apis", [])
    with pytest.raises(TypeError, match="Unsupported dataframe type"):
        Pipeline(cleaners=(Upper(),)).fit_transform(object())


def test_raw_dataframe_is_wrapped_by_registered_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "dataframe_apis", [PandasDataFrame])
    cleaned = Pipeline(cleaners=(Upper(),)).fit_transform(pd.DataFrame({"up_a": ["x"]}))
    assert isinstance(cleaned, PandasDataFrame)
    assert _values(cleaned, "up_a") == ["X"]


def test_auto_detect_false_runs_only_explicit_columns() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"up_a": ["x"], "other": ["y"]}))
    pipeline = Pipeline(
        cleaners=(Upper(),),
        column_cleaners={"other": Upper()},
        auto_detect=False,
    )

    cleaned = pipeline.fit_transform(df)

    assert _values(cleaned, "up_a") == ["x"]
    assert _values(cleaned, "other") == ["Y"]


def test_auto_detect_true_also_runs_detected_columns() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"up_a": ["x"], "other": ["y"]}))
    cleaned = Pipeline(cleaners=(Upper(),)).fit_transform(df)

    assert _values(cleaned, "up_a") == ["X"]
    assert _values(cleaned, "other") == ["y"]


def test_explicit_column_cleaner_overrides_detection() -> None:
    explicit = EmailCleaner()
    df = PandasDataFrame(df=pd.DataFrame({"country": ["A@B.COM"]}))
    cleaned = Pipeline(
        cleaners=(CountryCleaner(),), column_cleaners={"country": explicit}
    ).fit_transform(df)

    assert _values(cleaned, "country") == ["a@b.com"]


def test_ignore_cols_are_never_assigned() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"up_a": ["x"]}))
    cleaned = Pipeline(cleaners=(Upper(),), ignore_cols=["up_a"]).fit_transform(df)
    assert _values(cleaned, "up_a") == ["x"]


def test_missing_values_skip_clean_row() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"up_a": ["x", None, float("nan")]}))
    cleaned = Pipeline(cleaners=(Upper(),)).fit_transform(df)

    values = _values(cleaned, "up_a")
    assert values[0] == "X"
    assert values[1] is None or pd.isna(values[1])
    assert pd.isna(values[2])


def test_multi_input_row_with_missing_required_value_is_skipped() -> None:
    Shout.calls = []
    df = PandasDataFrame(
        df=pd.DataFrame({"first_col": ["a", None], "second_col": ["b", "c"]})
    )
    Pipeline(cleaners=(Shout(),)).fit_transform(df)

    assert set(Shout.calls) == {("a", "b")}


def test_multi_input_clean_row_called_once_per_row() -> None:
    Shout.calls = []
    df = PandasDataFrame(df=pd.DataFrame({"first_col": ["a"], "second_col": ["b"]}))
    Pipeline(cleaners=(Shout(),)).fit_transform(df)

    assert Shout.calls == [("a", "b")]


def test_auto_detect_false_drops_auto_match_scoring_one() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"up_a": ["x"]}))
    cleaned = Pipeline(cleaners=(UpperPerfect(),), auto_detect=False).fit_transform(df)
    assert _values(cleaned, "up_a") == ["x"]


def test_empty_pipeline_leaves_dataframe_unchanged() -> None:
    cleaned = Pipeline().fit_transform(PandasDataFrame(df=pd.DataFrame({"a": ["x"]})))
    assert _values(cleaned, "a") == ["x"]


def test_fit_transform_returns_same_wrapper_when_given_wrapper() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"a": ["x"]}))
    assert Pipeline().fit_transform(df) is df


def test_pipeline_can_be_reused_across_dataframes() -> None:
    pipeline = Pipeline(cleaners=(Upper(),))
    first = pipeline.fit_transform(PandasDataFrame(df=pd.DataFrame({"up_a": ["x"]})))
    second = pipeline.fit_transform(PandasDataFrame(df=pd.DataFrame({"up_b": ["y"]})))

    assert _values(first, "up_a") == ["X"]
    assert _values(second, "up_b") == ["Y"]
