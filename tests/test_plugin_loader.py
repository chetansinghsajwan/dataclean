import types
from collections.abc import Iterator

import pytest
from dataclean_pandas import PandasDataFrame
from dataclean_pandas.catalog import PandasCatalog

from dataclean import Cleaner, PluginInfo, config
from dataclean.plugins import PluginLoader
from dataclean.preset import Preset


class _Dist:
    def __init__(self, name: str) -> None:
        self.metadata = {"Name": name}


class _Preset(Preset):
    def match(self, ctx: Preset.MatchContext) -> float:
        return 0.0

    def get(self) -> dict[str, Cleaner]:
        return {}


@pytest.fixture(autouse=True)
def restore_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(config, "dataframe_apis", [])
    monkeypatch.setattr(config, "catalog_types", [])
    monkeypatch.setattr(config, "presets", [])
    yield


def _fake_module(monkeypatch: pytest.MonkeyPatch, info: object) -> list[str]:
    imported: list[str] = []
    module = types.SimpleNamespace(info=info)

    def fake_import(name: str) -> types.SimpleNamespace:
        imported.append(name)
        return module

    monkeypatch.setattr("importlib.import_module", fake_import)
    return imported


def test_find_plugins_returns_only_dataclean_prefixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dists = [_Dist("dataclean-foo"), _Dist("requests"), _Dist("dataclean-bar")]
    monkeypatch.setattr("importlib.metadata.distributions", lambda: dists)

    assert PluginLoader().find_plugins() == {"dataclean-foo", "dataclean-bar"}


def test_find_plugins_excludes_core_package_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.metadata.distributions", lambda: [_Dist("dataclean")]
    )

    assert PluginLoader().find_plugins() == set()


def test_load_plugin_registers_components_and_normalizes_module_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preset = _Preset()
    info = PluginInfo(
        name="dataclean-fake",
        dataframe_types={PandasDataFrame},
        catalog_types={PandasCatalog},
        presets={preset},
    )
    imported = _fake_module(monkeypatch, info)

    PluginLoader().load_plugin("dataclean-fake")

    assert imported == ["dataclean_fake"]
    assert config.dataframe_apis == [PandasDataFrame]
    assert config.catalog_types == [PandasCatalog]
    assert config.presets == [preset]


def test_load_plugin_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    info = PluginInfo(name="dataclean-fake", dataframe_types={PandasDataFrame})
    _fake_module(monkeypatch, info)

    loader = PluginLoader()
    loader.load_plugin("dataclean-fake")
    loader.load_plugin("dataclean-fake")

    assert config.dataframe_apis == [PandasDataFrame]


@pytest.mark.parametrize("bad_info", [None, "info", {"name": "x"}])
def test_load_plugin_invalid_info_raises(
    monkeypatch: pytest.MonkeyPatch, bad_info: object
) -> None:
    _fake_module(monkeypatch, bad_info)

    with pytest.raises(RuntimeError):
        PluginLoader().load_plugin("dataclean-fake")


def test_load_plugin_subclassed_info_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Sub(PluginInfo):
        pass

    _fake_module(monkeypatch, Sub(name="dataclean-fake"))

    with pytest.raises(RuntimeError):
        PluginLoader().load_plugin("dataclean-fake")


def test_load_plugins_loads_every_found_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = PluginLoader()
    monkeypatch.setattr(PluginLoader, "find_plugins", lambda self: {"a", "b"})
    loaded: list[str] = []
    monkeypatch.setattr(PluginLoader, "load_plugin", lambda self, n: loaded.append(n))

    loader.load_plugins()

    assert sorted(loaded) == ["a", "b"]
