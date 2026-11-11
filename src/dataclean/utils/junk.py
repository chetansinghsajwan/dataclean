"""Spot values that are code or markup, not data."""

import re

# Characters that real data in a text field does not hold: braces and "$" from
# templates and shell, "%" from format strings, ";" and "=" from SQL, "*" from
# SQL and globs, angle brackets from markup, a backslash from escapes and "@"
# from emails. A URL is spotted by "://". Decision: a value with any of them is
# treated as junk, not kept, since keeping an email or a template in a name
# column is never right. "&" is not here, as companies use it ("AT&T").
_JUNK_CHARS = re.compile(r"[{}<>$%;=*\\@]|://")

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


def looks_like_junk(text: str) -> bool:
    """Whether ``text`` looks like code, a template, markup, an email, a URL or filler.

    This is data hygiene, not a security check: it only decides that a value
    cannot be plain text such as a name, so a cleaner can null it.
    """
    return bool(_JUNK_CHARS.search(text) or _SQL.search(text) or _REPEATED.search(text))
