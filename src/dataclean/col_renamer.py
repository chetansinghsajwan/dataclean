from collections.abc import Callable
from dataclasses import dataclass
from typing import Iterable, Literal, get_args

import wordninja


@dataclass(frozen=True)
class ColRenamer:
    CaseTypes = Literal[
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

    _renamer: Callable[[tuple[str]], str] | None = None

    def __post_init__(self):

        assert isinstance(self.case, str), "case must be a string"

        assert self.case in get_args(self.CaseTypes), (
            f"case must be one of {get_args(self.CaseTypes)}"
        )

        object.__setattr__(self, "_renamer", self._get_renamer(self.case))

    def rename_cols(self, cols: Iterable[str]) -> dict[str, str]:

        rename_map = dict()
        for col in cols:
            new_col = self._renamer(self._get_words(col))

            if new_col != col:
                rename_map[col] = new_col

        return rename_map

    def rename(self, col: str) -> str:

        return self._renamer(self._get_words(col))

    def _get_renamer(self, case: CaseTypes) -> Callable[[tuple[str]], str]:
        if case == "snake":
            return self._snake_case_renamer
        elif case == "upper_snake":
            return self._upper_snake_case_renamer
        elif case == "upper":
            return self._upper_case_renamer
        elif case == "lower":
            return self._lower_case_renamer
        elif case == "pascal":
            return self._pascal_case_renamer
        elif case == "camel":
            return self._camel_case_renamer
        elif case == "kebab":
            return self._kebab_case_renamer
        elif case == "train":
            return self._train_case_renamer
        elif case == "cobol":
            return self._cobol_case_renamer
        else:
            raise ValueError(f"Unsupported case type: {case}")

    def _get_words(self, v: str) -> tuple[str]:
        return wordninja.split(v)

    def _snake_case_renamer(self, words: tuple[str]) -> str:
        return "_".join(word.lower() for word in words)

    def _upper_snake_case_renamer(self, words: tuple[str]) -> str:
        return "_".join(word.upper() for word in words)

    def _upper_case_renamer(self, words: tuple[str]) -> str:
        return "".join(word.upper() for word in words)

    def _lower_case_renamer(self, words: tuple[str]) -> str:
        return "".join(word.lower() for word in words)

    def _pascal_case_renamer(self, words: tuple[str]) -> str:
        return "".join(word.capitalize() for word in words)

    def _camel_case_renamer(self, words: tuple[str]) -> str:
        return "".join(
            word.capitalize() if i > 0 else word.lower() for i, word in enumerate(words)
        )

    def _kebab_case_renamer(self, words: tuple[str]) -> str:
        return "-".join(word.lower() for word in words)

    def _train_case_renamer(self, words: tuple[str]) -> str:
        return "-".join(word.capitalize() for word in words)

    def _cobol_case_renamer(self, words: tuple[str]) -> str:
        return "-".join(word.upper() for word in words)
