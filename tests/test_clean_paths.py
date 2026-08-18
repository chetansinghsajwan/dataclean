from collections.abc import Iterable

import pytest

from dataclean import Catalog, CleanPathResult, DataFrame, clean_paths, config


class DryRunCatalog(Catalog):
    def __init__(self) -> None:
        self.expanded_paths: list[str] = []

    def expand_paths(self, paths: Iterable[str]) -> set[str]:
        self.expanded_paths = list(paths)
        return {"dev.integration.clients"}

    def read_df(self, path: str) -> DataFrame:
        raise AssertionError("dry runs must not read dataframes")

    def write_df(self, df: DataFrame, path: str) -> None:
        raise AssertionError("dry runs must not write dataframes")


def test_clean_paths_dry_run_stops_before_reading_dataframes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "auto_load_plugins", False)
    catalog = DryRunCatalog()

    result = clean_paths(
        paths=["dev.integration.*"],
        write_path="dev_chetan_signh.*",
        catalog=catalog,
        dry_run=True,
    )

    assert catalog.expanded_paths == ["dev.integration.*"]
    assert isinstance(result, CleanPathResult)
