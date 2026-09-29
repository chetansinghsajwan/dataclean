"""Country cleaner for normalizing country names and codes to a canonical format."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, override

import pycountry
from rapidfuzz import fuzz, process

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner


@checked
class CountryCleaner(Cleaner):
    """Cleans and normalizes country names, alpha-2, and alpha-3 codes.

    Attempts to resolve each input value against pycountry's country
    database using a configurable pipeline of lookup strategies (exact
    alpha-2/alpha-3 code lookup, exact name lookup, and fuzzy name
    matching), then formats the resolved country according to
    ``out_format``.
    """

    @checked
    @dataclass
    class Details:
        """Resolved details for a single matched country.

        Attributes:
            name: The country's name.
            alpha2: The ISO 3166-1 alpha-2 code.
            alpha3: The ISO 3166-1 alpha-3 code.
        """

        name: str
        alpha2: str
        alpha3: str

    @checked
    class Format(StrEnum):
        """Input/output country representations supported by CountryCleaner."""

        AUTO = "auto"
        ALPHA2 = "alpha2"
        ALPHA3 = "alpha3"
        NAME = "name"
        NAME_FUZZY = "name_fuzzy"

    _AUTO_FORMATS: ClassVar[tuple[Format, ...]] = (
        Format.ALPHA2,
        Format.ALPHA3,
        Format.NAME,
        Format.NAME_FUZZY,
    )

    _PYCOUNTRY_COUNTRIES = {c.name.lower(): c for c in pycountry.countries}

    _in_formats: Format | tuple[Format, ...]
    _resolved_in_formats: tuple[Format, ...]
    _out_format: Format
    _find_country_pipeline: tuple[Callable[[str], Details | None], ...]
    _output_formatter: Callable[[Details], str]
    _fuzzy_match_thresold: float

    def __init__(
        self,
        in_format: Format | tuple[Format, ...] = Format.AUTO,
        out_format: Format = Format.NAME,
        fuzzy_match_thresold: float = 0.9,
        tags: tuple[str, ...] = (),
    ) -> None:
        """Initialize a CountryCleaner.

        Args:
            in_format: The input format(s) to attempt when resolving a
                value, tried in order. Format.AUTO expands to the full
                lookup pipeline (alpha2, alpha3, name, name_fuzzy). Defaults
                to Format.AUTO.
            out_format: The format used to render a resolved country.
                Defaults to Format.NAME.
            fuzzy_match_thresold: Minimum similarity ratio (0.0-1.0)
                required for a fuzzy name match to be accepted. Defaults to
                0.9.
            tags: Optional labels distinguishing multiple CountryCleaner
                instances.
        """
        super().__init__(tags=tags)

        self._in_formats = in_format
        self._out_format = out_format
        self._fuzzy_match_thresold = fuzzy_match_thresold
        self._resolved_in_formats = self._resolve_input_format(in_format)
        self._find_country_pipeline = self._create_find_country_pipeline(
            resolved_formats=self._resolved_in_formats
        )
        self._output_formatter = self._create_output_formatter(out_format)

    @property
    def in_formats(self) -> Format | tuple[Format, ...]:
        """Return the configured input format(s), as passed to __init__."""
        return self._in_formats

    @property
    def resolved_in_formats(self) -> tuple[Format, ...]:
        """Return the expanded, deduplicated input formats used for lookup."""
        return self._resolved_in_formats

    @property
    def out_format(self) -> Format:
        """Return the configured output format."""
        return self._out_format

    @override
    def _outputs(self) -> Cleaner.OutputSchema:
        """Return the output schema: a single column with the "country" role."""
        return Cleaner.OutputSchema(
            cols=(
                Cleaner.OutputSchema.Column(
                    roles=("country",),
                ),
            )
        )

    @override
    @checked
    def clean_row(self, v: str) -> str | None:
        """Clean a single country value.

        Args:
            v: The raw country value. Must be non-empty and have no leading
                or trailing whitespace.

        Returns:
            The formatted country (per out_format) if a lookup strategy in
            the resolved pipeline matches it, otherwise None.
        """

        assert len(v.strip()) > 0, "v must be a non-empty string"
        assert v.strip() == v, "v must not contain leading or trailing whitespace"

        v = v.lower()

        for finder in self._find_country_pipeline:
            country = finder(v)
            if country is not None:
                return self._output_formatter(country)

        return None

    @override
    def match_score(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        """Score confidence based on whether the column name contains "country".

        Args:
            df: The dataframe containing the candidate column (unused).
            cols: A single-element tuple with the candidate column name.

        Returns:
            MAX_SCORE if "country" appears in the column name (case
            insensitive), otherwise MIN_SCORE.
        """

        assert len(cols) == 1, "cols must be a tuple of length 1"

        if "country" in cols[0].lower():
            return Cleaner.MAX_SCORE

        return Cleaner.MIN_SCORE

    def _create_output_formatter(self, out_format: Format) -> Callable[[Details], str]:
        """Build the function that renders a resolved Details as out_format.

        Raises:
            ValueError: If out_format is not a supported output format
                (i.e. not NAME, ALPHA2, or ALPHA3).
        """
        match out_format:
            case self.Format.NAME:
                return lambda country: country.name
            case self.Format.ALPHA2:
                return lambda country: country.alpha2
            case self.Format.ALPHA3:
                return lambda country: country.alpha3

        raise ValueError(f"Unsupported out_format: {self._out_format}")

    @classmethod
    def _resolve_input_format(
        cls,
        fmt: Format | tuple[Format, ...],
    ) -> tuple[Format, ...]:
        """Expand AUTO and de-duplicate a requested input format.

        Args:
            fmt: A single format, or a tuple of formats (each of which may
                itself be AUTO), in the order they should be tried.

        Returns:
            A tuple of concrete (non-AUTO) formats, in first-seen order,
            with duplicates removed.
        """
        if fmt == CountryCleaner.Format.AUTO:
            return cls._AUTO_FORMATS

        if not isinstance(fmt, tuple):
            return (fmt,)

        seen: set[CountryCleaner.Format] = set()
        result: list[CountryCleaner.Format] = []
        for f in fmt:
            candidates = cls._AUTO_FORMATS if f == CountryCleaner.Format.AUTO else (f,)
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    result.append(c)

        return tuple(result)

    def _create_find_country_pipeline(
        self,
        resolved_formats: tuple[Format, ...],
    ) -> tuple[Callable[[str], Details | None], ...]:
        """Build the ordered lookup pipeline for resolved_formats.

        Args:
            resolved_formats: The concrete (non-AUTO) formats to attempt,
                in order.

        Returns:
            A tuple of lookup functions, each taking a lowercased value and
            returning matched Details or None.
        """

        pipeline = []
        for fmt in resolved_formats:
            match fmt:
                case self.Format.ALPHA2:
                    pipeline.append(CountryCleaner._find_country_alpha2)
                case self.Format.ALPHA3:
                    pipeline.append(CountryCleaner._find_country_alpha3)
                case self.Format.NAME:
                    pipeline.append(CountryCleaner._find_country_name)
                case self.Format.NAME_FUZZY:
                    pipeline.append(
                        lambda v: CountryCleaner._find_country_name_fuzzy(
                            v, self._fuzzy_match_thresold
                        )
                    )

        return tuple(pipeline)

    @staticmethod
    def _find_country_alpha2(v: str) -> Details | None:
        """Look up a country by exact ISO 3166-1 alpha-2 code (case-insensitive)."""
        result = pycountry.countries.get(alpha_2=v.upper())

        if result is None:
            return None

        return CountryCleaner.Details(
            name=result.name,
            alpha2=result.alpha_2,
            alpha3=result.alpha_3,
        )

    @staticmethod
    def _find_country_alpha3(v: str) -> Details | None:
        """Look up a country by exact ISO 3166-1 alpha-3 code (case-insensitive)."""
        result = pycountry.countries.get(alpha_3=v.upper())

        if result is None:
            return None

        return CountryCleaner.Details(
            name=result.name,
            alpha2=result.alpha_2,
            alpha3=result.alpha_3,
        )

    @staticmethod
    def _find_country_name(v: str) -> Details | None:
        """Look up a country via pycountry's built-in fuzzy name search.

        Returns None if no match is found.
        """
        try:
            result = pycountry.countries.search_fuzzy(v)[0]
        except (LookupError, IndexError):
            return None

        return CountryCleaner.Details(
            name=result.name,
            alpha2=result.alpha_2,
            alpha3=result.alpha_3,
        )

    @staticmethod
    def _find_country_name_fuzzy(v: str, threshold: float) -> Details | None:
        """Look up a country by fuzzy string matching against known country names.

        Args:
            v: The value to match.
            threshold: Minimum similarity ratio (0.0-1.0) required to
                accept the best match.

        Returns:
            The best-matching country's Details if its similarity score
            meets threshold, otherwise None.
        """
        name, score, _ = process.extractOne(
            v,
            CountryCleaner._PYCOUNTRY_COUNTRIES.keys(),
            scorer=fuzz.WRatio,
        )

        if score < (threshold * 100):
            return None

        country = CountryCleaner._PYCOUNTRY_COUNTRIES[name]

        return CountryCleaner.Details(
            name=country.name,
            alpha2=country.alpha_2,
            alpha3=country.alpha_3,
        )
