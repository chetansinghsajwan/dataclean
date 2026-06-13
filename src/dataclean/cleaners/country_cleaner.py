from collections.abc import Callable
from enum import Enum
from typing import ClassVar, Self, override

import pycountry
from pydantic import PrivateAttr, model_validator

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType
from dataclean.types import StrictBaseModel, strict_validate


class CountryCleaner(BaseCleaner, frozen=True):
    class Details(StrictBaseModel, frozen=True):
        name: str
        alpha2: str
        alpha3: str

    class Format(Enum):
        AUTO = "auto"
        NAME = "name"
        ALPHA2 = "alpha2"
        ALPHA3 = "alpha3"

    _AUTO_FORMATS: ClassVar[tuple[Format, ...]] = (
        Format.ALPHA2,
        Format.ALPHA3,
        Format.NAME,
    )

    in_format: Format | tuple[Format, ...] = Format.AUTO
    out_format: Format = Format.NAME

    # --- PRIVATE VARS ---

    _find_country_pipeline: tuple[Callable[[str], Details | None], ...] = PrivateAttr()

    # ---------------------------------------------------------------------------
    # INIT FUNCTIONS
    # ---------------------------------------------------------------------------

    @model_validator(mode="after")
    def _initialize(self) -> Self:
        self._find_country_pipeline = self._create_find_country_pipeline(self.in_format)

        return self

    # ---------------------------------------------------------------------------
    # PUBLIC FUNCTIONS
    # ---------------------------------------------------------------------------

    @override
    def name(self) -> str:
        return "CountryCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    @strict_validate
    def clean_value(self, v: str) -> str | None:
        country_match = self._find_country(v)
        return self._get_output(country_match) if country_match else None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        return 1.0 if "country" in cols[0].lower() else 0.0

    # ---------------------------------------------------------------------------
    # PRIVATE FUNCTIONS
    # ---------------------------------------------------------------------------

    def _find_country(self, v: str) -> Details | None:
        for finder in self._find_country_pipeline:
            country = finder(v)
            if country is not None:
                return country

        return None

    def _get_output(self, country: Details) -> str:
        match self.out_format:
            case self.Format.NAME:
                return country.name
            case self.Format.ALPHA2:
                return country.alpha2
            case self.Format.ALPHA3:
                return country.alpha3

        raise ValueError(f"Unsupported out_format: {self.out_format}")

    @classmethod
    def _resolve_input_format(
        cls,
        fmt: Format | tuple[Format, ...],
    ) -> tuple[Format, ...]:
        if fmt == CountryCleaner.Format.AUTO:
            return cls._AUTO_FORMATS

        if isinstance(fmt, tuple):
            resolved_set: set[CountryCleaner.Format] = set()
            for f in fmt:
                if f == CountryCleaner.Format.AUTO:
                    resolved_set.update(cls._AUTO_FORMATS)
                else:
                    resolved_set.add(f)
            return tuple(resolved_set)

        return (fmt,)

    def _create_find_country_pipeline(
        self,
        fmts: Format | tuple[Format, ...],
    ) -> tuple[Callable[[str], Details | None], ...]:

        def find_country_name(v: str) -> CountryCleaner.Details | None:
            try:
                result = pycountry.countries.search_fuzzy(v)[0]
            except (LookupError, IndexError):
                return None

            return CountryCleaner.Details(
                name=result.name,
                alpha2=result.alpha_2,
                alpha3=result.alpha_3,
            )

        def find_country_alpha2(v: str) -> CountryCleaner.Details | None:
            result = pycountry.countries.get(alpha_2=v.upper())

            if result is None:
                return None

            return CountryCleaner.Details(
                name=result.name,
                alpha2=result.alpha_2,
                alpha3=result.alpha_3,
            )

        def find_country_alpha3(v: str) -> CountryCleaner.Details | None:
            result = pycountry.countries.get(alpha_3=v.upper())

            if result is None:
                return None

            return CountryCleaner.Details(
                name=result.name,
                alpha2=result.alpha_2,
                alpha3=result.alpha_3,
            )

        in_formats = self._resolve_input_format(fmts)

        pipeline = []
        for fmt in in_formats:
            match fmt:
                case self.Format.NAME:
                    pipeline.append(find_country_name)
                case self.Format.ALPHA2:
                    pipeline.append(find_country_alpha2)
                case self.Format.ALPHA3:
                    pipeline.append(find_country_alpha3)

        return tuple(pipeline)
