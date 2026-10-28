"""Public entrypoints for cleaning dataframes and cataloged data paths.

Provides :func:`clean` (clean a single in-memory dataframe) and
:func:`clean_paths` (discover, read, clean, and write one or more dataframes
via a :class:`~dataclean.engine.Catalog`).
"""

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .cleaners import Cleaner
from .col_renamer import ColRenamer
from .config import config
from .engine import Catalog, DataFrame
from .pipeline import Pipeline
from .types import checked
from .utils import _log_args, map_paths

_logger = logging.getLogger(__name__)


def _find_catalog_type(name: str) -> type[Catalog] | None:
    """Find a registered catalog type matching ``name``.

    Matches case-insensitively against the catalog type's class name,
    either in full (e.g. ``"PandasCatalog"``) or with a trailing
    ``"Catalog"`` suffix dropped (e.g. ``"Pandas"``).
    """
    normalized = name.strip().lower()
    for catalog_type in config.catalog_types:
        class_name = catalog_type.__name__.lower()
        if class_name == normalized:
            return catalog_type

        if (
            class_name.endswith("catalog")
            and class_name.removesuffix("catalog") == normalized
        ):
            return catalog_type

    return None


def _resolve_catalog_by_name(name: str) -> Catalog:
    """Resolve and instantiate a registered catalog type by name.

    Raises:
        ValueError: If no registered catalog type matches ``name``, or the
            matched catalog type fails to instantiate.
    """
    catalog_type = _find_catalog_type(name)
    if catalog_type is None:
        raise ValueError(f"No registered catalog type matches {name!r}")

    _logger.info(
        "Instantiating catalog %s (matched %r)...", catalog_type.__name__, name
    )
    catalog = catalog_type.instantiate()
    if catalog is None:
        raise ValueError(f"Catalog {catalog_type.__name__} could not be instantiated")

    return catalog


@dataclass(frozen=True)
class _Target:
    """A path resolved to the catalog that owns it.

    Attributes:
        catalog: The catalog that reads/writes ``path``.
        scheme: The scheme prefix the user wrote ("" when none).
        path: The path with its scheme prefix stripped; what the catalog sees.
    """

    catalog: Catalog
    scheme: str
    path: str

    @property
    def full(self) -> str:
        """The path as the user wrote it, scheme prefix included."""
        return f"{self.scheme}:{self.path}" if self.scheme else self.path


class _CatalogRouter:
    """Route paths to catalogs by scheme prefix (``scheme:rest``).

    If ``fixed`` is given, every path goes to it unchanged (no scheme
    parsing). Otherwise the text before the first ``:`` selects the
    registered catalog type whose ``schemes`` contain it, and a path with no
    ``:`` goes to the catalog registered for the empty scheme. Catalogs are
    instantiated once per router.
    """

    def __init__(self, fixed: Catalog | None = None) -> None:
        self._fixed = fixed
        self._instances: dict[type[Catalog], Catalog] = {}

    def resolve(self, path: str) -> _Target:
        """Resolve ``path`` to its owning catalog.

        Raises:
            ValueError: If the scheme has no registered catalog, or the
                catalog cannot be instantiated.
        """
        if self._fixed is not None:
            return _Target(self._fixed, "", path)

        scheme, sep, rest = path.partition(":")
        if not sep:
            scheme, rest = "", path

        catalog_type = next(
            (t for t in config.catalog_types if scheme in t.schemes), None
        )
        if catalog_type is None:
            hint = (
                " (to use a local Windows drive path, prefix it, e.g. 'path:C:/data')"
                if len(scheme) == 1
                else ""
            )
            raise ValueError(
                f"No catalog registered for path scheme {scheme!r} in {path!r}{hint}"
            )

        catalog = self._instances.get(catalog_type)
        if catalog is None:
            _logger.debug("Instantiating catalog %s...", catalog_type.__name__)
            catalog = catalog_type.instantiate()
            if catalog is None:
                raise ValueError(
                    f"Catalog {catalog_type.__name__} could not be instantiated"
                )
            self._instances[catalog_type] = catalog
        return _Target(catalog, scheme, rest)


def _select_cleaners(names: Iterable[str] | None) -> list[Cleaner]:
    """Select the globally configured cleaners matching ``names``.

    Cleaners are matched by their display ``name`` (class name plus any
    tags) or plain class name. ``None`` selects every configured cleaner.

    Raises:
        ValueError: If a requested name matches no configured cleaner.
    """
    if names is None:
        return list(config.cleaners)

    remaining = set(names)
    selected = [
        cleaner
        for cleaner in config.cleaners
        if cleaner.name in remaining or type(cleaner).__name__ in remaining
    ]
    matched = {cleaner.name for cleaner in selected} | {
        type(cleaner).__name__ for cleaner in selected
    }
    unknown = remaining - matched
    if unknown:
        raise ValueError(f"Unknown cleaner(s): {', '.join(sorted(unknown))}")

    return selected


def clean(df, auto_detect: bool = True):
    """
    Clean a dataframe with automatic cleaner detection.

    If plugin auto-loading is enabled in the global config, installed
    plugins are loaded before building the cleaning pipeline.

    Args:
        df: DataFrame to clean (pandas, pyspark, or DataFrame-compatible).
        auto_detect: If True, auto-detect cleaners for columns.

    Returns:
        Cleaned DataFrame.

    Example:
        >>> import pandas as pd
        >>> from dataclean import clean
        >>> df = pd.DataFrame({"email": ["john.doe@example.com"]})
        >>> cleaned = clean(df)
    """

    if config.auto_load_plugins and config.plugin_loader is not None:
        _logger.info("Loading plugins...")
        config.plugin_loader.load_plugins()

    pipeline = Pipeline(
        cleaners=config.cleaners,
        auto_detect=auto_detect,
    )
    return pipeline.fit_transform(df)


@checked
@dataclass
class CleanPathResult:
    """Result of cleaning a path."""

    pass


def _clean_df(
    df: DataFrame,
    cleaners: Iterable[str] | None = None,
    ignore_cols: Iterable[str] | None = None,
) -> DataFrame:
    """Clean ``df``, with auto-detection enabled.

    Args:
        df: The dataframe to clean.
        cleaners: Names of cleaners to restrict cleaning to (see
            :func:`_select_cleaners`). If None, every globally configured
            cleaner is a candidate.
        ignore_cols: Columns to exclude from cleaning entirely.
    """

    pipeline = Pipeline(
        cleaners=_select_cleaners(cleaners),
        ignore_cols=ignore_cols,
        auto_detect=True,
    )
    return pipeline.fit_transform(df)


@checked
def clean_paths(
    paths: Iterable[str],
    write_path: str | None = None,
    catalog: Catalog | str | None = None,
    rename_cols: bool = True,
    rename_col_map: Mapping[str, str] | None = None,
    col_renamer: ColRenamer | None = None,
    clean_cols: bool = True,
    ignore_cols: Iterable[str] | None = None,
    use_global_config: bool = True,
    inplace: bool | None = None,
    cleaners: Iterable[str] | None = None,
    dry_run: bool = False,
) -> CleanPathResult:
    """Discover, clean, and write dataframes for a set of catalog paths.

    Expands ``paths`` (e.g. glob-style patterns) via ``catalog``, reads each
    resulting path as a :class:`~dataclean.engine.DataFrame`, cleans it
    (using the globally configured cleaners, with auto-detection enabled),
    and writes the cleaned result to the path(s) derived from
    ``write_path``. If ``catalog`` is not given, uses the global config's
    catalog (when ``use_global_config`` is True) or auto-detects one from
    the environment via the registered catalog types, trying them in
    priority order.

    Note:
        ``inplace`` is accepted and logged for diagnostics but is not yet
        threaded into the cleaning pipeline in this implementation.

    Args:
        paths: Path patterns to expand via the catalog.
        write_path: Template path (may contain ``*`` wildcards, see
            :func:`~dataclean.utils.paths.map_paths`) that each expanded
            path is mapped onto for writing the cleaned result. If
            ``None``, cleaned dataframes are not written.
        catalog: Catalog to use for expanding/reading/writing paths, or the
            name of a registered catalog type (matched case-insensitively
            against its class name, with or without a trailing "Catalog";
            e.g. ``"pandas"`` or ``"PandasCatalog"``). If ``None``, resolved
            from the global config or the environment.
        rename_cols: Whether to auto-rename columns using ``col_renamer``.
        rename_col_map: Explicit column rename mapping, applied after (and
            overriding) any automatic renaming from ``rename_cols``,
            regardless of whether ``rename_cols`` is enabled.
        col_renamer: :class:`ColRenamer` to use for auto-renaming columns.
            Defaults to the global config's renamer.
        clean_cols: Whether to clean column values via the cleaning
            pipeline. When False, dataframes are only (optionally) renamed
            and passed through unchanged.
        ignore_cols: Columns to exclude from cleaning.
        use_global_config: If True, fall back to the global config's
            catalog when ``catalog`` is not given.
        inplace: Whether to clean dataframes in place.
        cleaners: Names of cleaners to restrict cleaning to (matched
            against each cleaner's display name or class name). If
            ``None``, every globally configured cleaner is a candidate.
        dry_run: If True, skip reading and writing dataframes (path
            expansion/mapping and logging still occur, but no cleaning
            actually happens).

    Returns:
        A :class:`CleanPathResult` describing the outcome.

    Raises:
        ValueError: If no catalog is given and none can be resolved from
            the global config or the environment, if ``catalog`` is a name
            that matches no registered catalog type, or if ``cleaners``
            names an unknown cleaner.
    """

    _log_args(
        _logger,
        logging.DEBUG,
        paths=paths,
        write_path=write_path,
        catalog=catalog,
        rename_cols=rename_cols,
        rename_col_map=rename_col_map,
        col_renamer=col_renamer,
        clean_cols=clean_cols,
        ignore_cols=ignore_cols,
        inplace=inplace,
        use_global_config=use_global_config,
        cleaners=cleaners,
        dry_run=dry_run,
    )

    if config.auto_load_plugins and config.plugin_loader is not None:
        _logger.info("Loading plugins...")
        config.plugin_loader.load_plugins()

    if isinstance(catalog, str):
        catalog = _resolve_catalog_by_name(catalog)
    elif catalog is None and use_global_config:
        catalog = config.catalog

    router = _CatalogRouter(fixed=catalog)

    _logger.info("Expanding paths...")
    patterns_by_catalog: dict[int, tuple[_Target, list[str]]] = {}
    for pattern in paths:
        target = router.resolve(pattern)
        _, patterns = patterns_by_catalog.setdefault(id(target.catalog), (target, []))
        patterns.append(target.path)

    sources: dict[str, _Target] = {}
    for target, patterns in patterns_by_catalog.values():
        for expanded in sorted(target.catalog.expand_paths(patterns)):
            source = _Target(target.catalog, target.scheme, expanded)
            sources[source.full] = source
    expanded_paths_len = len(sources)
    expanded_paths_width = len(str(expanded_paths_len))

    _logger.debug("Expanded paths: %d", expanded_paths_len)
    if _logger.isEnabledFor(logging.DEBUG):
        for count, full in enumerate(sources, start=1):
            _logger.debug(
                "[%0*d/%d]\t%s",
                expanded_paths_width,
                count,
                expanded_paths_len,
                full,
            )

    write_targets: dict[str, _Target] = {}
    if write_path is not None:
        _logger.info("Mapping expanded paths to write paths...")
        dest = router.resolve(write_path)
        for full, source in sources.items():
            mapped = map_paths([source.path], dest.path)[source.path]
            write_targets[full] = _Target(dest.catalog, dest.scheme, mapped)
        write_paths_len = len(write_targets)
        write_paths_width = len(str(write_paths_len))

        _logger.debug("Write paths: %d", write_paths_len)
        if _logger.isEnabledFor(logging.DEBUG):
            for count, (src_full, write_target) in enumerate(
                write_targets.items(), start=1
            ):
                _logger.debug(
                    "[%0*d/%d]\t%s -> %s",
                    write_paths_width,
                    count,
                    write_paths_len,
                    src_full,
                    write_target.full,
                )

    renamer = col_renamer or config.col_renamer

    dfs: dict[str, DataFrame] = {}
    for count, (path, source) in enumerate(sources.items(), start=1):
        _logger.info(
            "[%0*d/%d] Reading path as dataframe: %s",
            expanded_paths_width,
            count,
            expanded_paths_len,
            path,
        )

        if not dry_run:
            df = source.catalog.read_df(source.path)

            rename_map: dict[str, str] = {}
            if rename_cols:
                rename_map.update(renamer.rename_cols(df.col_names()))
            if rename_col_map:
                rename_map.update(rename_col_map)
            if rename_map:
                _logger.debug("Renaming columns for '%s': %s", path, rename_map)
                df.rename_cols(rename_map)

            _logger.debug("Dataframe '%s': %s", path, df.cols())
            dfs[path] = df

    cleaned_dfs: dict[str, DataFrame] = {}
    for count, (path, df) in enumerate(dfs.items(), start=1):
        if clean_cols:
            _logger.info(
                "[%0*d/%d] Cleaning dataframe '%s'...",
                expanded_paths_width,
                count,
                expanded_paths_len,
                path,
            )
            cleaned_dfs[path] = _clean_df(
                df, cleaners=cleaners, ignore_cols=ignore_cols
            )
        else:
            cleaned_dfs[path] = df

        if write_path is None:
            continue

        write_target = write_targets[path]

        _logger.info(
            "[%0*d/%d] Writing dataframe to '%s'...",
            expanded_paths_width,
            count,
            expanded_paths_len,
            write_target.full,
        )

        if not dry_run:
            write_target.catalog.write_df(cleaned_dfs[path], write_target.path)

    return CleanPathResult()
