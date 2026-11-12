"""Tests for PluginLoader: plugin discovery by name and loading of plugin components into config."""

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
    """Plugins are installed packages whose names start with dataclean-. Of the
    packages installed, only those are picked up and unrelated ones like requests
    are left alone."""
    dists = [_Dist("dataclean-foo"), _Dist("requests"), _Dist("dataclean-bar")]
    monkeypatch.setattr("importlib.metadata.distributions", lambda: dists)

    assert PluginLoader().find_plugins() == {"dataclean-foo", "dataclean-bar"}


def test_find_plugins_excludes_core_package_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core package is itself called dataclean, but it is not a plugin. Discovery
    should not list it."""
    monkeypatch.setattr(
        "importlib.metadata.distributions", lambda: [_Dist("dataclean")]
    )

    assert PluginLoader().find_plugins() == set()


def test_load_plugin_registers_components_and_normalizes_module_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loading a plugin adds its data frame types, catalogs and presets to the shared
    config. Python can't import a name with a dash, so dataclean-fake is imported as
    dataclean_fake."""
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
    """Asking to load the same plugin twice should be harmless. Its components appear
    in the config once, not twice."""
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
    """Every plugin must expose a proper PluginInfo. If it exposes nothing useful, such
    as None, a string or a plain dict, loading fails with a clear error."""
    _fake_module(monkeypatch, bad_info)

    with pytest.raises(RuntimeError):
        PluginLoader().load_plugin("dataclean-fake")


def test_load_plugin_subclassed_info_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the exact PluginInfo type is accepted. A subclass could change how the info
    behaves, so it is refused."""

    class Sub(PluginInfo):
        pass

    _fake_module(monkeypatch, Sub(name="dataclean-fake"))

    with pytest.raises(RuntimeError):
        PluginLoader().load_plugin("dataclean-fake")


def test_load_plugins_loads_every_found_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_plugins is the convenience call. It asks discovery for the plugin names and
    loads each of them."""
    loader = PluginLoader()
    monkeypatch.setattr(PluginLoader, "find_plugins", lambda self: {"a", "b"})
    loaded: list[str] = []
    monkeypatch.setattr(PluginLoader, "load_plugin", lambda self, n: loaded.append(n))

    loader.load_plugins()

    assert sorted(loaded) == ["a", "b"]
