"""Tests mapping source table paths onto target paths with wildcards."""

import pytest

from dataclean.utils.paths import map_path, map_paths


@pytest.mark.parametrize(
    ("path", "to", "expected"),
    [
        (
            "dev.integration.clients",
            "dev_user.*",
            "dev_user.integration.clients",
        ),
        (
            "dev.integration.clients",
            "dev_user.test.*",
            "dev_user.test.clients",
        ),
        (
            "dev.integration.clients",
            "dev_user.test.test_*_test",
            "dev_user.test.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "dev_user.*.test_*_test",
            "dev_user.integration.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "*.*.test_*_test",
            "dev.integration.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "*.test_*_test",
            "dev.integration.test_clients_test",
        ),
    ],
)
def test_map_path(path: str, to: str, expected: str) -> None:
    """A target pattern decides which path parts are kept and which are replaced. It is
    how a table moves from one catalog or schema to another.
    """
    assert map_path(path, to, sep=".") == expected


@pytest.mark.parametrize(
    ("path", "to", "expected"),
    [
        (
            "dev.integration.clients",
            "dev_user.*",
            "dev_user.integration.clients",
        ),
        (
            "dev.integration.clients",
            "dev_user.test.*",
            "dev_user.test.clients",
        ),
        (
            "dev.integration.clients",
            "dev_user.test.test_*_test",
            "dev_user.test.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "dev_user.*.test_*_test",
            "dev_user.integration.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "*.*.test_*_test",
            "dev.integration.test_clients_test",
        ),
        (
            "dev.integration.clients",
            "*.test_*_test",
            "dev.integration.test_clients_test",
        ),
    ],
)
def test_map_paths(path: str, to: str, expected: str) -> None:
    """Mapping a list gives back a dict from each source path to its target. Callers
    can then look up what happened to any one path.
    """
    assert map_paths([path], to) == {path: expected}
