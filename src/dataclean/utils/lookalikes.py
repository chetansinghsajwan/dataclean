"""Spot values that look like code, a path or a link instead of plain text.

Whether such a value is junk depends on the column: a path is junk in a name
column but the point of a file-path column, and an email is junk in a name
column but the point of an email column. So each cleaner picks the checks it
needs; none of them is a general "is junk" test.
"""

import re

# Characters that real data in a text field does not hold: braces and "$" from
# templates and shell, "%" from format strings, ";" and "=" from SQL, "*" from
# SQL and globs, and angle brackets from markup. Decision: "&" is not here,
# as companies use it ("AT&T").
_CODE_CHARS = re.compile(r"[{}<>$%;=*]")

# SQL that carries no symbol above, such as "drop table users". Pairs of
# keywords are required so a lone "select" or "delete" stays a normal word.
_SQL = re.compile(
    r"\b(?:drop|truncate|alter)\s+(?:table|database|schema)\b"
    r"|\bunion\s+(?:all\s+)?select\b"
    r"|\bselect\b.+\bfrom\b"
    r"|\binsert\s+into\b"
    r"|\bdelete\s+from\b",
    re.IGNORECASE,
)

# The same character eight or more times in a row ("xxxxxxxx"), which is
# keyboard mashing or filler. Decision: no real name or company repeats a
# character this often.
_REPEATED = re.compile(r"(.)\1{7,}")

# A step up a directory ("../"), a path that starts at the root or home
# ("/etc/passwd", "~/x"), or any backslash (Windows paths and escapes).
# Decision: a "/" inside a value is not enough, since names such as "M/s
# Sharma Traders" and "AC/DC" use it.
_PATH = re.compile(r"\.\.[/\\]|^(?:/|~/)|\\")

# An email address ("@") or a URL ("://").
_LINK = re.compile(r"@|://")


def looks_like_code(text: str) -> bool:
    """Whether ``text`` looks like code, a template, SQL or filler.

    Suits plain-text columns such as names. It is data hygiene, not a security
    check: it only decides that a value cannot be ordinary text, so a cleaner
    can null it.
    """
    return bool(_CODE_CHARS.search(text) or _SQL.search(text) or _REPEATED.search(text))


def looks_like_path(text: str) -> bool:
    """Whether ``text`` looks like a file path or a path traversal.

    Suits columns that must not hold a path, such as names. Do not use it on
    file-path columns.
    """
    return bool(_PATH.search(text))


def looks_like_link(text: str) -> bool:
    """Whether ``text`` contains an email address or a URL.

    Suits columns that must not hold one, such as names. Do not use it on
    email or URL columns.
    """
    return bool(_LINK.search(text))


def looks_like_junk(text: str) -> bool:
    """Whether ``text`` looks like code, a link or a path.

    Decision: the name and address cleaners share this one test, so the two
    cannot drift apart on what counts as junk. Do not use it on columns whose
    point is a link or a path.
    """
    return looks_like_code(text) or looks_like_link(text) or looks_like_path(text)
