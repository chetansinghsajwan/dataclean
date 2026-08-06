"""Tests for the unified v1 cleaner pipeline."""

import pandas as pd
import pytest

from dataclean.cleaners.address_cleaner import AddressCleaner
from dataclean.cleaners.cleaner import Cleaner, ColumnRole
from dataclean.cleaners.country_cleaner import CountryCleaner
from dataclean.cleaners.phone_cleaner import PhoneCleaner
from dataclean.col_renamer import ColRenamer
from dataclean.engine.pandas import PandasDataFrame
from dataclean.pipeline import Assignment, Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver
from dataclean.pipeline.dependency_resolver import DependencyResolver
from dataclean.pipeline.entity_extractor import EntityExtractor


def test_cleaner_infers_primary_role() -> None:
    cleaner = CountryCleaner()
    assert cleaner.resolved_input_roles == (ColumnRole(key="value"),)


def test_cleaner_name_includes_configured_tags() -> None:
    cleaner = CountryCleaner(tags=("billing", "source-a"))
    assert cleaner.name == "CountryCleaner(billing, source-a)"


def test_explicit_roles_must_match_clean_row_signature() -> None:
    class InvalidCleaner(Cleaner, frozen=True):
        def output_schema(self) -> str:
            return "str"

        def input_roles(self) -> tuple[ColumnRole, ...]:
            return (ColumnRole(key="wrong"),)

        def clean_row(self, value: str) -> str:
            return value

    with pytest.raises(TypeError, match="same keys and order"):
        InvalidCleaner()


def test_resolver_handles_primary_and_group_cleaners() -> None:
    df = PandasDataFrame(
        df=pd.DataFrame(
            {
                "client_country": ["India"],
                "client_phone": ["+91 9876543210"],
                "address_line1": ["123 Main Street"],
            }
        )
    )
    resolver = Resolver((AddressCleaner(), CountryCleaner(), PhoneCleaner()))
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
    country = CountryCleaner()
    phone = PhoneCleaner(default_regions=("IN",))
    countries = (
        Assignment(country, {"value": "client_country"}, 1.0),
        Assignment(country, {"value": "manager_country"}, 1.0),
    )
    phone_assignment = Assignment(phone, {"value": "client_phone"}, 1.0)
    resolver = DependencyResolver(EntityExtractor(ColRenamer()._get_words))
    waves = resolver.resolve((*countries, phone_assignment))
    assert len(waves) == 2
    resolved_phone = next(item for item in waves[1] if item.cleaner is phone)
    assert resolved_phone.context_columns == {"country": "client_country"}


def test_pipeline_passes_context_as_positional_argument() -> None:
    pipeline = Pipeline(
        cleaners=(CountryCleaner(), PhoneCleaner(default_regions=("IN",))),
    )
    df = PandasDataFrame(
        df=pd.DataFrame({"client_country": ["IN"], "client_phone": ["9876543210"]})
    )
    cleaned = pipeline.fit_transform(df)
    assert cleaned.df["client_country"].tolist() == ["India"]
    assert cleaned.df["client_phone"].tolist() == ["+919876543210"]


def test_pipeline_wraps_pandas_dataframe() -> None:
    cleaned = Pipeline(cleaners=(CountryCleaner(),)).fit_transform(
        pd.DataFrame({"country": ["IN"]})
    )
    assert isinstance(cleaned, PandasDataFrame)
    assert cleaned.df["country"].tolist() == ["India"]


def test_address_cleaner_accepts_positional_input() -> None:
    result = AddressCleaner().clean_row(
        "Maharashtra", "India", "123 Main Street", "Mumbai", "400001"
    )
    assert result is not None
    assert result[0] == "India"
    assert result[2] == "400001"
