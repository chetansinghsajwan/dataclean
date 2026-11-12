"""Tests for the unified v1 cleaner pipeline."""

from typing import cast

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import AddressCleaner, Cleaner, ColRenamer, CountryCleaner, PhoneCleaner
from dataclean.pipeline import Assignment, Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver
from dataclean.pipeline.dependency_resolver import DependencyResolver
from dataclean.pipeline.entity_extractor import EntityExtractor


def test_cleaner_infers_primary_role() -> None:
    """A simple cleaner only has to write clean_row with one value parameter. From that signature we work out it has a single input column called value."""
    cleaner = CountryCleaner()
    assert cleaner.inputs.cols == (Cleaner.InputSchema.Column(key="value"),)


def test_cleaner_name_includes_configured_tags() -> None:
    """You may use the same cleaner several times, for example for billing and for another source. Tags are shown in its name, so you can tell the copies apart in logs."""
    cleaner = CountryCleaner(tags=("billing", "source-a"))
    assert cleaner.name == "CountryCleaner(billing, source-a)"


def test_explicit_roles_must_match_clean_row_signature() -> None:
    """If a cleaner declares its own input names, they must line up with the parameters of clean_row. Otherwise values would go to the wrong arguments, so a mismatch is rejected when it is created."""

    class InvalidCleaner(Cleaner):
        def _inputs(self) -> Cleaner.InputSchema:
            return Cleaner.InputSchema(cols=(Cleaner.InputSchema.Column(key="wrong"),))

        def clean_row(self, v: str) -> str:
            return v

    with pytest.raises(TypeError, match="same keys and order"):
        InvalidCleaner()


def test_resolver_handles_primary_and_group_cleaners() -> None:
    """Some cleaners take one column, others take a group such as an address. With both kinds registered, the resolver gives the group cleaner the address columns and gives the phone cleaner the client phone column."""
    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "client_country": ["India"],
                "client_phone": ["+91 9876543210"],
                "address_line1": ["123 Main Street"],
            }
        )
    )
    resolver = Resolver(cleaners=(AddressCleaner(), CountryCleaner(), PhoneCleaner()))
    assignments = resolver.resolve(df, set(df.col_names()))
    assert any(
        assignment.cleaner.name == "AddressCleaner" for assignment in assignments
    )
    assert any(
        assignment.cleaner.name == "PhoneCleaner"
        and assignment.role_columns["value"] == "client_phone"
        for assignment in assignments
    )


def test_dependency_resolver_uses_entity_matching_for_context() -> None:
    """The client phone should be read using the client country, not the manager country. The phone assignment therefore waits for the countries to run first, and picks client_country as its context."""
    country = CountryCleaner()
    phone = PhoneCleaner(default_regions=("IN",))
    countries = (
        Assignment(country, {"value": "client_country"}, 1.0),
        Assignment(country, {"value": "manager_country"}, 1.0),
    )
    phone_assignment = Assignment(phone, {"value": "client_phone"}, 1.0)
    resolver = DependencyResolver(
        entity_extractor=EntityExtractor(words_fn=ColRenamer()._get_words)
    )
    waves = resolver.resolve((*countries, phone_assignment))
    assert len(waves) == 2
    resolved_phone = next(item for item in waves[1] if item.cleaner is phone)
    assert resolved_phone.context_columns == {"country": "client_country"}


def test_pipeline_passes_context_as_positional_argument() -> None:
    """The phone cleaner needs the cleaned country to understand a local number. After a run, IN has become India and the number has the Indian country code in front."""
    pipeline = Pipeline(
        cleaners=(CountryCleaner(), PhoneCleaner(default_regions=("IN",))),
    )
    df = PandasDataFrame(
        df=pd.DataFrame({"client_country": ["IN"], "client_phone": ["9876543210"]})
    )

    cleaned = pipeline.fit_transform(df)

    cleaned_pd_df = cast(PandasDataFrame, cleaned)

    assert cleaned_pd_df.df["client_country"].tolist() == ["India"]
    assert cleaned_pd_df.df["client_phone"].tolist() == ["+919876543210"]


def test_pipeline_wraps_pandas_dataframe() -> None:
    """Users hand us ordinary pandas tables, and we should cope. The result comes back wrapped and the country value is cleaned."""
    cleaned = Pipeline(cleaners=(CountryCleaner(),)).fit_transform(
        pd.DataFrame({"country": ["IN"]})
    )
    assert isinstance(cleaned, PandasDataFrame)
    assert cleaned.df["country"].tolist() == ["India"]


def test_address_cleaner_accepts_positional_input() -> None:
    """Calling clean_row with plain positional values in schema order should work as well as using names. Here the state and postcode come out as given."""
    result = AddressCleaner().clean_row(
        "123 Main Street", None, None, "Mumbai", "Maharashtra", "400001"
    )
    assert result is not None
    assert result[0] == "Maharashtra"
    assert result[1] == "400001"
