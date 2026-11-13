"""Tell identifier columns from their names, for the cleaners that detect by value."""

# Words that end an id column name: "contact_id", "zip_code", "row_guid".
_ID_WORDS = frozenset(
    {"id", "ids", "guid", "uuid", "key", "code", "pin", "zip", "postcode", "pincode"}
)


def looks_like_id_name(words: tuple[str, ...]) -> bool:
    """Whether the column name says identifier or code.

    An id is never a quantity, a flag or a label, so the cleaners that guess by
    value (numbers, flags, enums) must leave such a column alone. They share
    this one check, so they cannot disagree about what an id column is.

    Decision: a copy number after a separator ("contacttypeid_2", "user id 3")
    is ignored, since a second set of id columns is still ids and must not be
    cleaned as a number or a flag.

    Args:
        words: The lowercase words of the column name.

    Returns:
        True when the name ends in an id word such as ``id`` or ``code``.
    """
    while words and words[-1].isdigit():
        words = words[:-1]
    return bool(words) and words[-1] in _ID_WORDS
