"""Cleaner for normalizing free-form text (HTML, URLs, whitespace, etc.)."""

import html
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import ClassVar, override

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils.null_tokens import (
    COMMON_NULL_TOKENS,
    is_null_token,
    null_token_set,
)

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
        remove_symbols: If True, strips symbols such as currency signs, math signs,
            emoji and the copyright sign. Punctuation is kept; use
            ``remove_punctuation`` to strip both.
        replace_newlines_with_spaces: If True, replaces control characters
            (including newlines) with a single space; if False, drops most
            control characters but keeps newlines out of the subsequent
            whitespace-collapsing step by removing them explicitly.
        decode_entities: If True, decodes HTML entities such as `&amp;` and
            `&#39;` to the characters they stand for. Only entities that end
            with a semicolon are decoded, so text like `AT&T` is left alone.
        remove_invisible: If True, removes the byte-order mark, zero-width space and
            word joiner. They are invisible but make equal-looking values differ.
            The zero-width joiner and non-joiner are kept because Indic and
            Persian scripts and emoji sequences need them.
        normalize_unicode: If True, converts text to Unicode NFC form so that
            equal-looking values (for example `e` plus a combining accent and the
            single character `\u00e9`) compare equal.
        max_combining_marks: Most combining marks kept on a single character. Extra
            marks are dropped, which removes stacked-mark "zalgo" text. Spacing
            marks used by Indic scripts are not counted. None keeps every mark.
        null_tokens: Placeholder values (compared case-insensitively after
            cleaning) that mean "no value" and become None.
        infinity_as_null: If True, `inf` and `infinity` (with an optional sign)
            are also treated as placeholders. They usually come from
            float serialization, not from real text.
    """

    lowercase: bool = True
    remove_html: bool = True
    remove_urls: bool = False
    remove_emails: bool = False
    remove_punctuation: bool = False
    remove_digits: bool = False
    remove_symbols: bool = False
    replace_newlines_with_spaces: bool = True
    decode_entities: bool = True
    remove_invisible: bool = True
    normalize_unicode: bool = True
    max_combining_marks: int | None = 2
    null_tokens: tuple[str, ...] = COMMON_NULL_TOKENS
    infinity_as_null: bool = True

    _HTML_RE: ClassVar[re.Pattern] = re.compile(
        r"<!--.*?-->|<[!?][^<>]*>|</?[A-Za-z][^<>]*>", re.DOTALL
    )
    _URL_RE: ClassVar[re.Pattern] = re.compile(r"http[s]?://\S+|www\.\S+")
    _EMAIL_RE: ClassVar[re.Pattern] = re.compile(r"\S+@\S+")
    _DIGIT_RE: ClassVar[re.Pattern] = re.compile(r"\d+")
    _PUNCT_RE: ClassVar[re.Pattern] = re.compile(r"[^\w\s]")
    _MULTI_SPACE_RE: ClassVar[re.Pattern] = re.compile(r"\s+")
    _NL_SPACE_RE: ClassVar[re.Pattern] = re.compile(r"[\x00-\x1f\x7f-\x9f]")
    _NL_STRIP_RE: ClassVar[re.Pattern] = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
    _INVISIBLE_RE: ClassVar[re.Pattern] = re.compile("[\ufeff\u200b\u2060]")
    _ENTITY_RE: ClassVar[re.Pattern] = re.compile(
        r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);"
    )
    _INFINITY_TOKENS: ClassVar[tuple[str, ...]] = (
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
    )

    _pipeline: tuple[Callable[[str], str], ...] = ()
    _null_set: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Initialize base cleaner state, then build the regex step pipeline."""
        super().__post_init__()
        self._pipeline = self._build_pipeline()
        tokens = set(self.null_tokens)
        if self.infinity_as_null:
            tokens.update(self._INFINITY_TOKENS)
        self._null_set = null_token_set(tokens)

    def _build_pipeline(self) -> tuple[Callable[[str], str], ...]:
        """Evaluate configuration flags once and build a linear regex step pipeline.

        Returns:
            An ordered tuple of ``str -> str`` steps to apply to each value,
            reflecting which cleaning flags are enabled. Whitespace
            collapsing is always included as the final structural step,
            followed by lowercasing if ``lowercase`` is set.
        """
        steps: list[Callable[[str], str]] = []

        if self.remove_invisible:
            steps.append(lambda x: self._INVISIBLE_RE.sub("", x))

        if self.remove_html:
            steps.append(lambda x: self._HTML_RE.sub(" ", x))

        if self.decode_entities:
            steps.append(lambda x: self._ENTITY_RE.sub(self._decode_entity, x))

        if self.normalize_unicode:
            steps.append(lambda x: unicodedata.normalize("NFC", x))

        if self.max_combining_marks is not None:
            steps.append(self._limit_combining_marks)

        if self.remove_urls:
            steps.append(lambda x: self._URL_RE.sub("", x))

        if self.remove_emails:
            steps.append(lambda x: self._EMAIL_RE.sub("", x))

        if self.remove_digits:
            steps.append(lambda x: self._DIGIT_RE.sub("", x))

        if self.remove_symbols:
            steps.append(self._strip_symbols)

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

    def _limit_combining_marks(self, value: str) -> str:
        """Drop combining marks beyond ``max_combining_marks`` on one character."""
        limit = self.max_combining_marks
        if limit is None or value.isascii():
            return value
        kept: list[str] = []
        run = 0
        for char in value:
            if unicodedata.category(char) in ("Mn", "Me"):
                run += 1
                if run > limit:
                    continue
            else:
                run = 0
            kept.append(char)
        return "".join(kept)

    @staticmethod
    def _strip_symbols(value: str) -> str:
        """Drop characters in the Unicode symbol categories (Sm, Sc, Sk, So)."""
        if value.isascii() and value.isalnum():
            return value
        return "".join(
            char for char in value if not unicodedata.category(char).startswith("S")
        )

    @staticmethod
    def _decode_entity(match: re.Match) -> str:
        """Decode one matched HTML entity, leaving unknown ones as written."""
        return html.unescape(match.group(0))

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Run ``v`` through the configured cleaning pipeline.

        Args:
            v: The raw text to clean.

        Returns:
            The cleaned text, or None if the pipeline reduces it to an
            empty string or a placeholder from ``null_tokens``.
        """

        # 🚀 Linear Pipeline Execution
        for step in self._pipeline:
            v = step(v)

        if is_null_token(v, self._null_set):
            return None
        return v

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
