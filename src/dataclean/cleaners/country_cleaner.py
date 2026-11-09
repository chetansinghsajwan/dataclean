"""Country cleaner for normalizing country names and codes to a canonical format."""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, override

import pycountry
from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner

# Names people use that pycountry does not list. They are added on top of the
# official, common and short names pycountry has.
_ALIASES: dict[str, tuple[str, ...]] = {
    "AE": ("uae", "emirates"),
    "BR": ("brasil",),
    "CI": ("ivory coast",),
    "CV": ("cape verde",),
    "CZ": ("czech republic",),
    "DE": ("deutschland",),
    "ES": ("espana",),
    "GB": ("uk", "great britain", "britain", "england", "scotland", "wales"),
    "IN": ("bharat", "hindustan"),
    "MK": ("macedonia",),
    "MM": ("burma",),
    "NL": ("holland",),
    "PS": ("palestine",),
    "RU": ("russia",),
    "SZ": ("swaziland",),
    "TL": ("east timor",),
    "TR": ("turkey",),
    "US": ("usa", "america", "united states of america"),
    "VA": ("vatican", "vatican city"),
}

# Names that point at more than one country. They become None instead of a guess.
_AMBIGUOUS_NAMES: frozenset[str] = frozenset({"korea", "congo"})

# Everyday names for countries whose pycountry names are formal and that have
# no common name there.
_COMMON_NAMES: dict[str, str] = {
    "CD": "DR Congo",
    "PS": "Palestine",
    "RU": "Russia",
}

# Fuzzy matching is skipped for values shorter than this: one wrong letter in a
# short word, such as "man" for "oman", changes the country.
_MIN_FUZZY_LENGTH = 5


def _normalize_name(value: str) -> str:
    """Fold case, accents, dots and a leading "the" so equal names compare equal."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("&", " and ").replace(".", "")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return value.removeprefix("the ")


def _build_name_index() -> dict[str, str]:
    """Map each normalized country name to its alpha-2 code, dropping ambiguous names."""
    seen: dict[str, set[str]] = {}
    for country in pycountry.countries:
        names = [country.name]
        names += [
            getattr(country, attr)
            for attr in ("common_name", "official_name")
            if hasattr(country, attr)
        ]
        names += _ALIASES.get(country.alpha_2, ())
        for name in names:
            seen.setdefault(_normalize_name(name), set()).add(country.alpha_2)

    return {
        name: next(iter(codes))
        for name, codes in seen.items()
        if len(codes) == 1 and name not in _AMBIGUOUS_NAMES
    }


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
            name: The country's ISO 3166-1 name, such as "Korea, Republic of".
            common_name: The everyday name, such as "South Korea", when it
                differs from ``name``.
            alpha2: The ISO 3166-1 alpha-2 code.
            alpha3: The ISO 3166-1 alpha-3 code.
        """

        name: str
        alpha2: str
        alpha3: str
        common_name: str | None = None

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

    _NAME_INDEX: ClassVar[dict[str, str]] = _build_name_index()

    _in_formats: Format | tuple[Format, ...]
    _resolved_in_formats: tuple[Format, ...]
    _out_format: Format
    _find_country_pipeline: tuple[Callable[[str], Details | None], ...]
    _output_formatter: Callable[[Details], str]
    _fuzzy_match_thresold: float
    _common_names: bool

    def __init__(
        self,
        in_format: Format | tuple[Format, ...] = Format.AUTO,
        out_format: Format = Format.NAME,
        fuzzy_match_thresold: float = 0.9,
        common_names: bool = True,
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
            common_names: If True, ``Format.NAME`` output uses the everyday
                name ("South Korea") where one exists; if False, the ISO
                name ("Korea, Republic of"). Defaults to True.
            tags: Optional labels distinguishing multiple CountryCleaner
                instances.
        """
        super().__init__(tags=tags)

        self._in_formats = in_format
        self._out_format = out_format
        self._fuzzy_match_thresold = fuzzy_match_thresold
        self._common_names = common_names
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
                if self._common_names:
                    return lambda country: country.common_name or country.name
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
    def _details(country: Any) -> Details:
        """Build Details from a pycountry country record."""
        return CountryCleaner.Details(
            name=country.name,
            alpha2=country.alpha_2,
            alpha3=country.alpha_3,
            common_name=getattr(country, "common_name", None)
            or _COMMON_NAMES.get(country.alpha_2),
        )

    @staticmethod
    def _find_country_alpha2(v: str) -> Details | None:
        """Look up a country by exact ISO 3166-1 alpha-2 code (case-insensitive)."""
        result = pycountry.countries.get(alpha_2=v.upper())
        return None if result is None else CountryCleaner._details(result)

    @staticmethod
    def _find_country_alpha3(v: str) -> Details | None:
        """Look up a country by exact ISO 3166-1 alpha-3 code (case-insensitive)."""
        result = pycountry.countries.get(alpha_3=v.upper())
        return None if result is None else CountryCleaner._details(result)

    @staticmethod
    def _find_country_name(v: str) -> Details | None:
        """Look up a country by its exact name, ignoring case, accents and dots.

        Matches the ISO, common and official names and a few aliases such as
        "USA" or "Deutschland". Names shared by two countries, such as "Korea",
        give None.
        """
        alpha2 = CountryCleaner._NAME_INDEX.get(_normalize_name(v))
        if alpha2 is None:
            return None
        return CountryCleaner._details(pycountry.countries.get(alpha_2=alpha2))

    @staticmethod
    def _find_country_name_one_edit(v: str) -> Details | None:
        """Look up a country whose name is one edit away from ``v``.

        The similarity score counts a swapped pair of letters ("indai") as two
        edits and rejects it, so this accepts one edit, where a swap counts as
        one. It needs exactly one country within that distance.
        """
        codes = {
            CountryCleaner._NAME_INDEX[name]
            for name, _, _ in process.extract(
                v,
                CountryCleaner._NAME_INDEX.keys(),
                scorer=OSA.distance,
                score_cutoff=1,
                limit=None,
            )
        }
        if len(codes) != 1:
            return None
        return CountryCleaner._details(pycountry.countries.get(alpha_2=codes.pop()))

    @staticmethod
    def _find_country_name_fuzzy(v: str, threshold: float) -> Details | None:
        """Look up a country by fuzzy string matching against known country names.

        Args:
            v: The value to match.
            threshold: Minimum similarity ratio (0.0-1.0) required to
                accept the best match.

        Returns:
            The best-matching country's Details if its similarity score
            meets threshold, otherwise None. Values shorter than
            ``_MIN_FUZZY_LENGTH`` characters never match.
        """
        v = _normalize_name(v)
        if len(v) < _MIN_FUZZY_LENGTH or v in _AMBIGUOUS_NAMES:
            return None

        match = process.extractOne(
            v, CountryCleaner._NAME_INDEX.keys(), scorer=fuzz.WRatio
        )
        if match is None or match[1] < (threshold * 100):
            return CountryCleaner._find_country_name_one_edit(v)

        return CountryCleaner._details(
            pycountry.countries.get(alpha_2=CountryCleaner._NAME_INDEX[match[0]])
        )
