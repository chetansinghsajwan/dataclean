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


class Recorder(Cleaner):
    """Records exactly what clean_row receives."""

    seen: list[str | None] = []

    def clean_row(self, value: str | None = None) -> str | None:
        Recorder.seen.append(value)
        return value


def test_blank_and_whitespace_values_never_reach_a_required_cleaner() -> None:
    Shout.calls = []
    df = PandasDataFrame(
        df=pd.DataFrame(
            {"first_col": ["", "  ", " a "], "second_col": ["b", "c", " d "]}
        )
    )
    cleaned = Pipeline(cleaners=(Shout(),)).fit_transform(df)

    assert set(Shout.calls) == {("a", "d")}
    values = _values(cleaned, "first_col")
    assert values[:2] == [None, None] or all(pd.isna(v) for v in values[:2])
    assert values[2] == "ad"


def test_optional_inputs_are_normalized_too() -> None:
    Recorder.seen = []
    df = PandasDataFrame(df=pd.DataFrame({"value_col": ["", " x ", "  "]}))
    Pipeline(
        column_cleaners={"value_col": Recorder()}, auto_detect=False
    ).fit_transform(df)

    assert set(Recorder.seen) <= {None, "x"}
    assert "x" in Recorder.seen


def test_non_string_values_pass_through_unchanged() -> None:
    from dataclean.pipeline.pipeline import _normalize

    assert _normalize(5) == 5
    assert _normalize(True) is True
    assert _normalize(None) is None
    assert _normalize(float("nan")) is None
    assert _normalize("  a b ") == "a b"
    assert _normalize("") is None
    assert _normalize("   ") is None


def test_pipeline_cleans_every_phone_column_alongside_country() -> None:
    from dataclean import PhoneCleaner

    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "tel": ["9876543210"],
                "mobile": ["9123456780"],
                "fax": ["9876543211"],
                "country": ["IN"],
                "dlcountryoforigin": ["IN"],
            }
        )
    )
    cleaned = Pipeline(
        cleaners=(CountryCleaner(), PhoneCleaner(default_regions=("IN",)))
    ).fit_transform(df)

    assert _values(cleaned, "tel") == ["+919876543210"]
    assert _values(cleaned, "mobile") == ["+919123456780"]
    assert _values(cleaned, "fax") == ["+919876543211"]
    assert _values(cleaned, "country") == ["India"]


def test_multi_output_columns_are_named_after_the_first_required_input() -> None:
    from dataclean import AddressCleaner

    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "county": ["Kent"],
                "address1": ["12 High Street"],
                "address2": ["Bromley"],
                "postcode": ["br1 1aa"],
            }
        )
    )
    cleaned = Pipeline(cleaners=(AddressCleaner(),)).fit_transform(df)

    names = {name for name, _ in cleaned.cols()}
    assert {
        "address1_street_cleaned",
        "address1_house_no_cleaned",
        "address1_postcode_cleaned",
    } <= names
    assert not any(name.startswith("county_") for name in names)


def test_phone_uses_the_country_column_when_several_country_columns_exist() -> None:
    from dataclean import PhoneCleaner

    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "tel": ["020 7946 0958", "9876543210"],
                "country": ["United Kingdom", "India"],
                "_client_country_of_incorporation": ["Malta", "Malta"],
            }
        )
    )

    cleaned = Pipeline(cleaners=(CountryCleaner(), PhoneCleaner())).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["tel"].tolist() == ["+442079460958", "+919876543210"]


def test_username_column_is_left_untouched_by_the_default_cleaners() -> None:
    from dataclean.config import config

    df = PandasDataFrame(df=pd.DataFrame({"username": ["JSmith2", "  j.smith  "]}))

    cleaned = Pipeline(cleaners=tuple(config.cleaners)).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["username"].tolist() == ["JSmith2", "  j.smith  "]


# ==============================================================================
# KEEP ORIGINAL
# ==============================================================================


def test_keep_original_copies_in_place_columns_before_cleaning() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"email": [" A@B.COM ", "junk"]}))

    cleaned = Pipeline(cleaners=(EmailCleaner(),), keep_original=True).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["email"].tolist() == ["a@b.com", None]
    assert cleaned.df["email_uncleaned"].tolist() == [" A@B.COM ", "junk"]


def test_keep_original_is_off_by_default() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"email": ["A@B.COM"]}))

    cleaned = Pipeline(cleaners=(EmailCleaner(),)).fit_transform(df)

    assert cleaned.df is not None
    assert list(cleaned.df.columns) == ["email"]


def test_keep_original_suffix_is_configurable() -> None:
    df = PandasDataFrame(df=pd.DataFrame({"email": ["A@B.COM"]}))

    cleaned = Pipeline(
        cleaners=(EmailCleaner(),), keep_original=True, original_suffix="_raw"
    ).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["email_raw"].tolist() == ["A@B.COM"]


def test_keep_original_leaves_uncleaned_and_added_columns_alone() -> None:
    from dataclean import AddressCleaner

    df = PandasDataFrame(
        df=pd.DataFrame(
            {"address1": ["12 High Street"], "postcode": ["br1 1aa"], "note": ["x"]}
        )
    )

    cleaned = Pipeline(
        cleaners=(AddressCleaner(),), keep_original=True, ignore_cols=["note"]
    ).fit_transform(df)

    assert cleaned.df is not None
    assert not any(col.endswith("_uncleaned") for col in cleaned.df.columns)


def test_keep_original_copies_before_context_cleaners_run() -> None:
    from dataclean import PhoneCleaner

    df = PandasDataFrame(
        df=pd.DataFrame({"tel": ["020 7946 0958"], "country": ["united kingdom"]})
    )

    cleaned = Pipeline(
        cleaners=(PhoneCleaner(), CountryCleaner()), keep_original=True
    ).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["tel_uncleaned"].tolist() == ["020 7946 0958"]
    assert cleaned.df["country_uncleaned"].tolist() == ["united kingdom"]
    assert cleaned.df["tel"].tolist() == ["+442079460958"]


def test_keep_original_rejects_a_name_collision() -> None:
    from dataclean.pipeline.exceptions import PipelineConfigError

    df = PandasDataFrame(
        df=pd.DataFrame({"email": ["A@B.COM"], "email_uncleaned": ["taken"]})
    )

    with pytest.raises(PipelineConfigError, match="email_uncleaned"):
        Pipeline(cleaners=(EmailCleaner(),), keep_original=True).fit_transform(df)
