"""Tests for the shared id-column name check."""

import pytest

from dataclean.utils import looks_like_id_name


@pytest.mark.parametrize(
    "name",
    [
        "id",
        "contactid",
        "contact_id",
        "companyid",
        "rowguid",
        "postcode",
        "zip_code",
        "Contact_ID",
        "contacttypeid_2",
        "companyid_3",
        "user_id_2",
        "order id 10",
        "contacttype_id3",
    ],
)
def test_looks_like_id_name_true(name: str) -> None:
    assert looks_like_id_name(name)


@pytest.mark.parametrize(
    "name", ["paid", "valid", "amount", "creditlimit", "age", "optout", "col_2"]
)
def test_looks_like_id_name_false(name: str) -> None:
    assert not looks_like_id_name(name)
