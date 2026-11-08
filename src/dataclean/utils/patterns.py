"""Helpers for expanding path patterns (literal, glob or regex) into paths."""

import glob
import os
import re
from collections.abc import Iterable

REGEX_PREFIX = "re:"

# Characters that start a glob wildcard.
_GLOB_CHARS = frozenset("*?[")

# Characters that make a regex stop being a literal path prefix.
_REGEX_META = frozenset("\\.^$*+?{}[]()|")


def is_regex(pattern: str) -> bool:
    """Return whether ``pattern`` is a regex, written with the ``re:`` prefix."""
    return pattern.startswith(REGEX_PREFIX)


def compile_regex(pattern: str) -> re.Pattern[str]:
    """Compile the regex of a ``re:`` pattern.

    Raises:
        ValueError: If the pattern is not a valid regex.
    """
    try:
        return re.compile(pattern.removeprefix(REGEX_PREFIX))
    except re.error as error:
        raise ValueError(f"Invalid regex pattern '{pattern}': {error}") from error


def has_glob(pattern: str) -> bool:
    """Return whether ``pattern`` holds a glob wildcard (``*``, ``?`` or ``[``)."""
    return any(char in _GLOB_CHARS for char in pattern)


def expand_local_paths(patterns: Iterable[str]) -> set[str]:
    """Expand path patterns against the local file system.

    Each pattern is one of:

    - A literal path, returned as it is without checking that it exists, so a
      missing file fails later with the reader's own error.
    - A glob (``*``, ``?``, ``[...]`` and ``**`` for any depth), expanded to the
      files it matches.
    - A regex, written ``re:<regex>``, which must match a whole file path
      written with ``/``. Files are searched below the directory the regex
      starts with literally, or the working directory if there is none.

    Args:
        patterns: The patterns to expand.

    Returns:
        The set of concrete paths the patterns stand for.

    Raises:
        ValueError: If a regex pattern is not a valid regex.
    """
    paths: set[str] = set()
    for pattern in patterns:
        if is_regex(pattern):
            paths.update(_expand_regex(pattern))
        elif has_glob(pattern):
            paths.update(
                path
                for path in glob.glob(pattern, recursive=True)
                if os.path.isfile(path)
            )
        else:
            paths.add(pattern)
    return paths


def _expand_regex(pattern: str) -> set[str]:
    """Return the files below the regex's literal directory that it matches."""
    regex = compile_regex(pattern)
    body = pattern.removeprefix(REGEX_PREFIX)

    literal = ""
    for char in body:
        if char in _REGEX_META:
            break
        literal += char
    root = literal.rpartition("/")[0] if "/" in literal else ""
    if not root and literal.startswith("/"):
        root = "/"

    matches: set[str] = set()
    for directory, _, files in os.walk(root or "."):
        for name in files:
            path = os.path.join(directory, name).replace(os.sep, "/")
            if root == "" and path.startswith("./"):
                path = path[2:]
            if regex.fullmatch(path):
                matches.add(path)
    return matches
