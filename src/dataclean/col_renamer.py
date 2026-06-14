from collections.abc import Callable, Iterable
from typing import Literal
import wordninja
from pydantic import PrivateAttr, model_validator
from dataclean.types import StrictBaseModel


class ColRenamer(StrictBaseModel, frozen=True):
    type CaseTypes = Literal[
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

    _renamer: Callable[[tuple[str, ...]], str] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _set_renamer_engine(self) -> "ColRenamer":
        self._renamer = self._get_renamer(self.case)
        return self

    def rename_cols(self, cols: Iterable[str]) -> dict[str, str]:
        rename_map = {}
        for col in cols:
            new_col = self._renamer(self._get_words(col))
            if new_col != col:
                rename_map[col] = new_col
        return rename_map

    def rename(self, col: str) -> str:
        return self._renamer(self._get_words(col))

    def _get_renamer(self, case: str) -> Callable[[tuple[str, ...]], str]:
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
        return tuple(wordninja.split(v))

    def _snake_case_renamer(self, words: tuple[str, ...]) -> str:
        return "_".join(word.lower() for word in words)

    def _upper_snake_case_renamer(self, words: tuple[str, ...]) -> str:
        return "_".join(word.upper() for word in words)

    def _upper_case_renamer(self, words: tuple[str, ...]) -> str:
        return "".join(word.upper() for word in words)

    def _lower_case_renamer(self, words: tuple[str, ...]) -> str:
        return "".join(word.lower() for word in words)

    def _pascal_case_renamer(self, words: tuple[str, ...]) -> str:
        return "".join(word.capitalize() for word in words)

    def _camel_case_renamer(self, words: tuple[str, ...]) -> str:
        return "".join(
            word.capitalize() if i > 0 else word.lower() for i, word in enumerate(words)
        )

    def _kebab_case_renamer(self, words: tuple[str, ...]) -> str:
        return "-".join(word.lower() for word in words)

    def _train_case_renamer(self, words: tuple[str, ...]) -> str:
        return "-".join(word.capitalize() for word in words)

    def _cobol_case_renamer(self, words: tuple[str, ...]) -> str:
        return "-".join(word.upper() for word in words)
