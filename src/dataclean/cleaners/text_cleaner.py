"""Cleaner for normalizing free-form text (HTML, URLs, whitespace, etc.)."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import ClassVar, override

from dataclean.engine import DataFrame
from dataclean.types import checked

from .cleaner import Cleaner


@checked
@dataclass
class TextCleaner(Cleaner):
    """Normalizes free-form text by stripping noise and collapsing whitespace.

    Configuration flags select which regex-based steps are compiled into a
    linear pipeline (built once in ``__post_init__``); each incoming value
    is then run through that pipeline in ``clean_row``.

    Attributes:
        lowercase: If True, lowercases the text as the final step.
        remove_html: If True, strips HTML tags.
        remove_urls: If True, strips http(s):// and www. URLs.
        remove_emails: If True, strips email-shaped substrings.
        remove_punctuation: If True, strips non-word, non-whitespace
            characters.
        remove_digits: If True, strips digit runs.
        replace_newlines_with_spaces: If True, replaces control characters
            (including newlines) with a single space; if False, drops most
            control characters but keeps newlines out of the subsequent
            whitespace-collapsing step by removing them explicitly.
    """

    lowercase: bool = True
    remove_html: bool = True
    remove_urls: bool = True
    remove_emails: bool = True
    remove_punctuation: bool = False
    remove_digits: bool = False
    replace_newlines_with_spaces: bool = True

    _HTML_RE: ClassVar[re.Pattern] = re.compile(r"<[^>]+>")
    _URL_RE: ClassVar[re.Pattern] = re.compile(r"http[s]?://\S+|www\.\S+")
    _EMAIL_RE: ClassVar[re.Pattern] = re.compile(r"\S+@\S+")
    _DIGIT_RE: ClassVar[re.Pattern] = re.compile(r"\d+")
    _PUNCT_RE: ClassVar[re.Pattern] = re.compile(r"[^\w\s]")
    _MULTI_SPACE_RE: ClassVar[re.Pattern] = re.compile(r"\s+")
    _NL_SPACE_RE: ClassVar[re.Pattern] = re.compile(r"[\x00-\x1f\x7f-\x9f]")
    _NL_STRIP_RE: ClassVar[re.Pattern] = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

    _pipeline: tuple[Callable[[str], str], ...] = ()

    def __post_init__(self) -> None:
        """Initialize base cleaner state, then build the regex step pipeline."""
        super().__post_init__()
        self._pipeline = self._build_pipeline()

    def _build_pipeline(self) -> tuple[Callable[[str], str], ...]:
        """Evaluate configuration flags once and build a linear regex step pipeline.

        Returns:
            An ordered tuple of ``str -> str`` steps to apply to each value,
            reflecting which cleaning flags are enabled. Whitespace
            collapsing is always included as the final structural step,
            followed by lowercasing if ``lowercase`` is set.
        """
        steps: list[Callable[[str], str]] = []

        if self.remove_html:
            steps.append(lambda x: self._HTML_RE.sub(" ", x))

        if self.remove_urls:
            steps.append(lambda x: self._URL_RE.sub("", x))

        if self.remove_emails:
            steps.append(lambda x: self._EMAIL_RE.sub("", x))

        if self.remove_digits:
            steps.append(lambda x: self._DIGIT_RE.sub("", x))

        if self.remove_punctuation:
            steps.append(lambda x: self._PUNCT_RE.sub("", x))

        if self.replace_newlines_with_spaces:
            steps.append(lambda x: self._NL_SPACE_RE.sub(" ", x))
        else:
            # 🚀 THE FIX: Explicitly drop '\n' so it isn't caught by \s+ in the next step
            steps.append(lambda x: self._NL_STRIP_RE.sub("", x).replace("\n", ""))

        # Always collapse spaces as the final structural cleanup
        steps.append(lambda x: self._MULTI_SPACE_RE.sub(" ", x).strip())

        if self.lowercase:
            steps.append(lambda x: x.lower())

        return tuple(steps)

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Run ``v`` through the configured cleaning pipeline.

        Args:
            v: The raw text to clean.

        Returns:
            The cleaned text, or None if the pipeline reduces it to an
            empty string.
        """

        # 🚀 Linear Pipeline Execution
        for step in self._pipeline:
            v = step(v)

        return v if v else None

    @override
    def match_score(self, df: DataFrame, cols: Iterable[str]) -> float:
        """Score confidence based on the column name looking text-related.

        Args:
            df: The dataframe being inspected (unused; scoring here is
                name-based only).
            cols: Candidate column name(s); only the first is considered.

        Returns:
            0.8 if the column name contains a free-text-related token
            (text, description, comment, etc.), otherwise 0.1 as a low
            baseline confidence.
        """
        if not tuple(cols):
            return 0.0
        cols_tuple = tuple(cols)
        if any(
            token in cols_tuple[0].lower()
            for token in (
                "text",
                "description",
                "comment",
                "notes",
                "summary",
                "review",
            )
        ):
            return 0.8
        return 0.1
