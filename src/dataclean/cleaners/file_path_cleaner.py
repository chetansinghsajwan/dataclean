"""Cleaner for normalizing file names and file paths."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, override

from dataclean.engine import DataFrame
from dataclean.types import checked
from dataclean.utils import has_words, remove_invisible

from .cleaner import Cleaner

# Characters that carry no text but sneak into copied values.

# Characters no common file system accepts in a name. A colon is allowed only
# in a drive prefix such as "C:", checked separately.
_FORBIDDEN = re.compile(r'[<>"|?*\x00-\x1f\x7f]')

# A Windows drive letter such as ``C:`` before a slash or at the end.
_DRIVE = re.compile(r"[A-Za-z]:(?=/|$)")

# A file extension at the end of a name: a dot after at least one character,
# then up to 10 letters or digits.
_EXTENSION = re.compile(r"(?<=[^/.])\.([A-Za-z0-9]{1,10})$")

# Name hints: words that mark a path column, and words that mean the column
# holds another kind of value.
_NAME_TOKENS = ("file", "path", "dir", "folder", "directory")
_OTHER_KINDS = ("url", "uri", "link", "href", "id")


@checked
@dataclass
class FilePathCleaner(Cleaner):
    """Normalizes a file name or file path, tolerating common surface noise.

    Trims whitespace, invisible characters and wrapping quotes (as pasted by
    "Copy as path"), turns backslashes into ``separator``, collapses repeated
    separators (a leading pair, as in ``\\\\server\\share``, is kept), drops
    ``.`` segments in the middle of a path and lowercases the file extension
    (``IMG_01.PNG`` becomes ``IMG_01.png``). The name itself keeps its case,
    since file systems may tell ``Report`` and ``report`` apart. ``..``
    segments are kept, because resolving them needs the real directory.

    A value that is empty, that holds control characters or any of
    ``< > " | ? *``, or a colon outside a drive prefix, becomes None. So does
    a value that is only dots, separators or a drive, since no file is named
    by it.

    Attributes:
        separator: The path separator to write, ``/`` or ``\\``.
        lowercase_extension: If True, lowercases the file extension.
    """

    separator: Literal["/", "\\"] = "/"
    lowercase_extension: bool = True

    @override
    def clean_row(self, v: str) -> str | None:  # type: ignore
        """Clean ``v`` into a normalized file name or path.

        Args:
            v: The raw file name or path.

        Returns:
            The normalized value, or None if ``v`` is not a usable file name
            or path.
        """
        path = remove_invisible(v).strip().strip("\"'").strip()
        path = path.replace("\\", "/")
        if not path or _FORBIDDEN.search(path):
            return None

        drive = ""
        if _DRIVE.match(path):
            drive, path = path[:2], path[2:]
        if ":" in path:
            return None

        # Keep a leading "//" (network share), collapse every other run.
        lead = "//" if path.startswith("//") and not path.startswith("///") else ""
        path = lead + re.sub(r"/{2,}", "/", path[len(lead) :])
        path = re.sub(r"(?<=/)(?:\./)+", "", path)

        if set(path) <= {".", "/"}:
            return None
        if self.lowercase_extension:
            path = _EXTENSION.sub(lambda match: f".{match.group(1).lower()}", path)
        return (drive + path).replace("/", self.separator)

    @override
    def match_score(
        self, df: DataFrame, cols: Iterable[str], words: tuple[str, ...]
    ) -> float:
        """Score confidence from the column name looking file-related.

        Args:
            df: The dataframe being inspected (unused; scoring is name-based).
            cols: Candidate column name(s); only the first is considered.
            words: The lowercase words of the column name, split with the same aliases for every cleaner.

        Returns:
            1.0 if the name has a ``file``, ``path``, ``dir``, ``folder`` or
            ``directory`` word, else 0.0. A
            name with a ``url``, ``uri``, ``link``, ``href`` or ``id`` word,
            such as ``url_path`` or ``file_id``, scores 0.0.
        """
        cols_tuple = tuple(cols)
        if not cols_tuple:
            return 0.0
        if any(has_words(words, hint) for hint in _OTHER_KINDS):
            return 0.0
        if any(has_words(words, hint) for hint in _NAME_TOKENS):
            return 1.0
        return 0.0
