"""Tell identifier columns from their names, for the cleaners that detect by value."""

import re

# A name that ends in "id", "guid", "key", "code" and similar. A glued word such
# as "contactid" needs a letter before the ending, so "paid" and "valid" are
# listed apart as words that only look like ids.
_ID_NAME = re.compile(
    r"(?:^|[^a-z0-9])(?:id|guid|uuid|key|code|pin|zip|postcode|pincode)$"
    r"|(?<=[a-z])(?:id|guid|uuid|code|postcode|pincode)$"
)
_NOT_ID_WORDS = ("paid", "valid", "void", "humid")

# A copy number after a separator: "contacttypeid_2", "user id 3".
_COPY_NUMBER = re.compile(r"[^a-z0-9]?\d+$")


def looks_like_id_name(col_name: str) -> bool:
    """Whether the column name says identifier or code.

    An id is never a quantity, a flag or a label, so the cleaners that guess by
    value (numbers, flags, enums) must leave such a column alone. They share
    this one check, so they cannot disagree about what an id column is.

    Decision: a copy number after a separator ("contacttypeid_2", "user id 3")
    is ignored, since a second set of id columns is still ids and must not be
    cleaned as a number or a flag.

    Args:
        col_name: The column name, in any case.

    Returns:
        True when the name ends in an id word such as ``id`` or ``code``.
    """
    name = _COPY_NUMBER.sub("", col_name.lower())
    if name.endswith(_NOT_ID_WORDS):
        return False
    return _ID_NAME.search(name) is not None
