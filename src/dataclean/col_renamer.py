"""Column name renaming: cleans column names, splits them into words and
re-joins them in a chosen naming convention (snake_case, camelCase, kebab-case,
etc.).
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from .types import checked
from .utils.emoji import remove_emoji
from .utils.invisible import remove_invisible, replace_control_chars
from .utils.markup import strip_html
from .utils.words import split_words

# Names that word splitting gets wrong: abbreviations it would cut into single
# letters (``fname`` -> ``f``, ``name``) and compounds it leaves whole. Each key
# is a lowercase name, mapped to the words it stands for.
DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "fname": ("first", "name"),
    "mname": ("middle", "name"),
    "lname": ("last", "name"),
    "lnamefname": ("last", "name", "first", "name"),
    "guid": ("guid",),
    "rowguid": ("row", "guid"),
    "dob": ("date", "of", "birth"),
    "dateofbirth": ("date", "of", "birth"),
    "postcode": ("post", "code"),
    "filename": ("file", "name"),
    "username": ("user", "name"),
}

_SEPARATORS = re.compile(r"[^A-Za-z0-9]+")


@checked
@dataclass
class ColRenamer:
    """Cleans column names and renames them into a consistent casing convention.

    Each name is first cleaned of invisible characters, emoji, markup and
    accents, then split into words using ``split_words`` (which can split
    concatenated/no-delimiter names, e.g. ``"firstname"`` -> ``("first",
    "name")``) and rejoined using the renaming strategy for ``case``. Special
    characters such as ``#``, ``%`` or ``.`` act as word breaks.

    Names that start with a digit, or that clean down to nothing, get
    ``prefix`` as a leading word. In ``rename_cols``, names that end up the
    same are told apart with a numeric word (``phone``, ``phone_2``).

    Attributes:
        case: The target casing convention; one of the values in
            :data:`CaseTypes`. Defaults to ``"snake"``.
        prefix: Word put in front of a name that starts with a digit or is
            empty, so the result is a usable identifier.
        max_length: Longest name to produce, for engines that limit it, or
            None for no limit.
        aliases: Lowercase names mapped to the words they stand for, used
            instead of word splitting. A custom value replaces
            :data:`DEFAULT_ALIASES`; pass ``{}`` to turn aliases off.
    """

    CaseTypes: ClassVar = Literal[
        "snake",
        "upper_snake",
        "upper",
        "lower",
        "pascal",
        "camel",
        "kebab",
        "train",
        "cobol",
    ]

    case: CaseTypes = "snake"
    prefix: str = "col"
    max_length: int | None = None
    aliases: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_ALIASES)
    )
    _renamer: Callable[[tuple[str, ...]], str] = lambda v: ""

    def __post_init__(self) -> None:
        """Resolve and cache the word-joining function for ``self.case``."""
        self._renamer = self._get_renamer(self.case)

    def rename_cols(self, cols: Iterable[str]) -> dict[str, str]:
        """Compute renames for the given column names.

        Args:
            cols: Column names to consider renaming.

        Returns:
            Mapping of old name to new name, containing only the columns
            whose renamed form differs from the original.
        """
        cols = tuple(cols)
        targets = {col: self._fit(self._usable_words(col)) for col in cols}

        # Decision: a column that keeps its name reserves it first, so a
        # column renamed onto the same name is the one that gets the suffix.
        used = {col for col, target in targets.items() if col == target}
        rename_map = {}
        for col, target in targets.items():
            if col == target:
                continue
            words = self._usable_words(col)
            n = 2
            while target in used:
                target = self._fit(words + (str(n),))
                n += 1
            used.add(target)
            rename_map[col] = target
        return rename_map

    def rename(self, col: str) -> str:
        """Return ``col`` cleaned and renamed into ``self.case``, regardless of whether it changes."""
        return self._fit(self._usable_words(col))

    def _usable_words(self, col: str) -> tuple[str, ...]:
        """Return the words of ``col``, with ``prefix`` added if it would not be a valid name."""
        words = self._get_words(col)
        if not words or words[0][0].isdigit():
            return (self.prefix, *words)
        return words

    def _fit(self, words: tuple[str, ...]) -> str:
        """Join ``words`` in ``self.case`` and cut the result to ``max_length``."""
        name = self._renamer(words)
        if self.max_length is None or len(name) <= self.max_length:
            return name
        # Decision: keep a numeric last word (the dedupe suffix) and cut the
        # words before it, so shortened names stay different.
        if words[-1].isdigit() and len(words) > 1:
            tail = self._renamer(("x", words[-1]))[1:]
            head = self._renamer(words[:-1])[: max(self.max_length - len(tail), 1)]
            return head + tail
        return name[: self.max_length]

    def _get_renamer(self, case: str) -> Callable[[tuple[str, ...]], str]:
        """Look up the word-joining function for the given case name."""
        maps = {
            "snake": self._snake_case_renamer,
            "upper_snake": self._upper_snake_case_renamer,
            "upper": self._upper_case_renamer,
            "lower": self._lower_case_renamer,
            "pascal": self._pascal_case_renamer,
            "camel": self._camel_case_renamer,
            "kebab": self._kebab_case_renamer,
            "train": self._train_case_renamer,
            "cobol": self._cobol_case_renamer,
        }
        return maps[case]

    def _get_words(self, v: str) -> tuple[str, ...]:
        """Clean ``v`` and split it into words using ``split_words``."""
        v = replace_control_chars(remove_invisible(remove_emoji(strip_html(v))))
        # Decision: fold accents (``Café`` -> ``Cafe``) because word splitting
        # treats a non-ASCII letter as a break and would cut the word in two.
        v = "".join(
            ch
            for ch in unicodedata.normalize("NFKD", v)
            if not unicodedata.combining(ch)
        )
        # Decision: aliases are looked up per piece between separators, so
        # ``fname_2`` and ``FName`` both match ``fname``.
        words: list[str] = []
        for piece in filter(None, _SEPARATORS.split(v)):
            alias = self.aliases.get(piece.lower())
            words.extend(alias if alias is not None else split_words(piece))
        return tuple(words)

    def _snake_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``snake_case``."""
        return "_".join(word.lower() for word in words)

    def _upper_snake_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``UPPER_SNAKE_CASE``."""
        return "_".join(word.upper() for word in words)

    def _upper_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``UPPERCASE`` with no separator."""
        return "".join(word.upper() for word in words)

    def _lower_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``lowercase`` with no separator."""
        return "".join(word.lower() for word in words)

    def _pascal_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``PascalCase``."""
        return "".join(word.capitalize() for word in words)

    def _camel_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``camelCase``."""
        return "".join(
            word.capitalize() if i > 0 else word.lower() for i, word in enumerate(words)
        )

    def _kebab_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``kebab-case``."""
        return "-".join(word.lower() for word in words)

    def _train_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``Train-Case``."""
        return "-".join(word.capitalize() for word in words)

    def _cobol_case_renamer(self, words: tuple[str, ...]) -> str:
        """Join ``words`` as ``COBOL-CASE``."""
        return "-".join(word.upper() for word in words)
