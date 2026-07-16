import re
from collections.abc import Callable
from typing import Any, ClassVar, Self, override

from pydantic import PrivateAttr, model_validator

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.engine.dataframe import DataFrame, DataType


class TextCleaner(BaseCleaner, frozen=True):
    lowercase: bool = True
    remove_html: bool = True
    remove_urls: bool = True
    remove_emails: bool = True
    remove_punctuation: bool = False
    remove_digits: bool = False
    replace_newlines_with_spaces: bool = True

    _HTML_RE: ClassVar[re.Pattern] = re.compile(r'<[^>]+>')
    _URL_RE: ClassVar[re.Pattern] = re.compile(r'http[s]?://\S+|www\.\S+')
    _EMAIL_RE: ClassVar[re.Pattern] = re.compile(r'\S+@\S+')
    _DIGIT_RE: ClassVar[re.Pattern] = re.compile(r'\d+')
    _PUNCT_RE: ClassVar[re.Pattern] = re.compile(r'[^\w\s]')
    _MULTI_SPACE_RE: ClassVar[re.Pattern] = re.compile(r'\s+')
    _NL_SPACE_RE: ClassVar[re.Pattern] = re.compile(r'[\x00-\x1f\x7f-\x9f]')
    _NL_STRIP_RE: ClassVar[re.Pattern] = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')

    _pipeline: tuple[Callable[[str], str], ...] = PrivateAttr()

    @model_validator(mode="after")
    def _build_pipeline(self) -> Self:
        """Evaluates configurations once and builds a linear regex execution pipeline."""
        steps: list[Callable[[str], str]] = []

        if self.remove_html:
            steps.append(lambda x: self._HTML_RE.sub(' ', x))

        if self.remove_urls:
            steps.append(lambda x: self._URL_RE.sub('', x))

        if self.remove_emails:
            steps.append(lambda x: self._EMAIL_RE.sub('', x))

        if self.remove_digits:
            steps.append(lambda x: self._DIGIT_RE.sub('', x))

        if self.remove_punctuation:
            steps.append(lambda x: self._PUNCT_RE.sub('', x))

        if self.replace_newlines_with_spaces:
            steps.append(lambda x: self._NL_SPACE_RE.sub(' ', x))
        else:
            # 🚀 THE FIX: Explicitly drop '\n' so it isn't caught by \s+ in the next step
            steps.append(lambda x: self._NL_STRIP_RE.sub('', x).replace('\n', ''))

        # Always collapse spaces as the final structural cleanup
        steps.append(lambda x: self._MULTI_SPACE_RE.sub(' ', x).strip())

        if self.lowercase:
            steps.append(lambda x: x.lower())

        self._pipeline = tuple(steps)
        return self

    @override
    def name(self) -> str:
        return "TextCleaner"

    @override
    def output_schema(self) -> DataType | tuple[tuple[str, DataType], ...]:
        return "str"

    @override
    def clean_value(self, v: Any) -> str | None:
        if not isinstance(v, str):
            return None

        normalized = v

        # 🚀 Linear Pipeline Execution
        for step in self._pipeline:
            normalized = step(normalized)

        return normalized if normalized else None

    @override
    def get_data_type_confidence(self, df: DataFrame, cols: tuple[str, ...]) -> float:
        if not cols:
            return 0.0
        if any(token in cols[0].lower() for token in ("text", "description", "comment", "notes", "summary", "review")):
            return 0.8
        return 0.1
