"""Column name renaming: splits column names into words and re-joins them
in a chosen naming convention (snake_case, camelCase, kebab-case, etc.).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import ClassVar, Literal

import wordninja

from .types import checked


@checked
@dataclass
class ColRenamer:
    """Renames column names into a consistent casing convention.

    Splits each column name into words using ``wordninja`` (which can split
    concatenated/no-delimiter names, e.g. ``"firstname"`` -> ``("first",
    "name")``) and rejoins the words using the renaming strategy for
    ``case``.

    Attributes:
        case: The target casing convention; one of the values in
            :data:`CaseTypes`. Defaults to ``"lower"``.
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

    case: CaseTypes = "lower"
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
        assert self._renamer is not None
        rename_map = {}
        for col in cols:
            new_col = self._renamer(self._get_words(col))
            if new_col != col:
                rename_map[col] = new_col
        return rename_map

    def rename(self, col: str) -> str:
        """Return ``col`` renamed into ``self.case``, regardless of whether it changes."""
        return self._renamer(self._get_words(col))

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
        """Split ``v`` into words using ``wordninja``."""
        return tuple(wordninja.split(v))

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
