"""Public entrypoints for cleaning dataframes and cataloged data paths.

Provides :func:`clean` (clean a single in-memory dataframe) and
:func:`clean_paths` (discover, read, clean, and write one or more dataframes
via a :class:`~dataclean.engine.Catalog`).
"""

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .col_renamer import ColRenamer
from .config import config
from .engine import Catalog, DataFrame
from .pipeline import Pipeline
from .types import checked
from .utils import _log_args, map_paths

_logger = logging.getLogger(__name__)


def _catalog_name(catalog: Catalog | type[Catalog] | None) -> str:
    """Return a human-readable name for ``catalog``, for logging purposes."""
    if catalog is None:
        return "None"

    if isinstance(catalog, type):
        return catalog.__name__

    return catalog.__class__.__name__


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


def _clean_df(df: DataFrame) -> DataFrame:
    """Clean ``df`` using the globally configured cleaners, with auto-detection enabled."""

    pipeline = Pipeline(
        cleaners=config.cleaners,
        auto_detect=True,
    )
    return pipeline.fit_transform(df)


@checked
def clean_paths(
    paths: Iterable[str],
    write_path: str | None = None,
    catalog: Catalog | None = None,
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
        ``rename_cols``, ``rename_col_map``, ``col_renamer``, ``clean_cols``,
        ``ignore_cols``, ``inplace``, and ``cleaners`` are accepted and
        logged for diagnostics but are not yet threaded into the cleaning
        pipeline in this implementation; cleaning currently always uses the
        global config's cleaners with auto-detection.

    Args:
        paths: Path patterns to expand via the catalog.
        write_path: Template path (may contain ``*`` wildcards, see
            :func:`~dataclean.utils.paths.map_paths`) that each expanded
            path is mapped onto for writing the cleaned result. If
            ``None``, cleaned dataframes are not written.
        catalog: Catalog to use for expanding/reading/writing paths. If
            ``None``, resolved from the global config or the environment.
        rename_cols: Whether to rename columns.
        rename_col_map: Explicit column rename mapping.
        col_renamer: :class:`ColRenamer` to use for renaming columns.
        clean_cols: Whether to clean columns.
        ignore_cols: Columns to exclude from cleaning.
        use_global_config: If True, fall back to the global config's
            catalog when ``catalog`` is not given.
        inplace: Whether to clean dataframes in place.
        cleaners: Names of cleaners to restrict cleaning to.
        dry_run: If True, skip reading and writing dataframes (path
            expansion/mapping and logging still occur, but no cleaning
            actually happens).

    Returns:
        A :class:`CleanPathResult` describing the outcome.

    Raises:
        ValueError: If no catalog is given and none can be resolved from
            the global config or the environment.
    """

    _log_args(
        _logger,
        logging.DEBUG,
        paths=paths,
        write_path=write_path,
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

    if catalog is None:
        if use_global_config and config.catalog is not None:
            _logger.info("No catalog provided, using global config...")
            catalog = config.catalog

        else:
            _logger.info("No catalog provided, trying to load from environment...")

            catalog_types_len = len(config.catalog_types)
            width = len(str(catalog_types_len))
            for count, catalog_type in enumerate(config.catalog_types, start=1):
                _logger.debug(
                    "[%0*d/%d] Checking if catalog type %s supports environment...",
                    width,
                    count,
                    catalog_types_len,
                    _catalog_name(catalog_type),
                )

                if catalog_type.supports_env():
                    _logger.debug(
                        "Instantiating catalog %s...", _catalog_name(catalog_type)
                    )
                    catalog = catalog_type.instantiate()

                    if catalog is None:
                        _logger.warning(
                            "Catalog type %s supports environment variables, but instantiation failed.",
                            _catalog_name(catalog_type),
                        )
                        continue

                    _logger.debug(
                        "Instantiating catalog %s done.", _catalog_name(catalog_type)
                    )
                    break

            if catalog is None:
                raise ValueError("catalog must be provided")

    _logger.info("Expanding paths...")
    expanded_paths = catalog.expand_paths(paths)
    expanded_paths_len = len(expanded_paths)
    expanded_paths_width = len(str(expanded_paths_len))

    _logger.debug("Expanded paths: %d", expanded_paths_len)
    if _logger.isEnabledFor(logging.DEBUG):
        for count, path in enumerate(expanded_paths, start=1):
            _logger.debug(
                "[%0*d/%d]\t%s",
                expanded_paths_width,
                count,
                expanded_paths_len,
                path,
            )

    if write_path is not None:
        _logger.info("Mapping expanded paths to write paths...")
        write_paths = map_paths(expanded_paths, write_path)
        write_paths_len = len(write_paths)
        write_paths_width = len(str(write_paths_len))

        _logger.debug("Write paths: %d", write_paths_len)
        if _logger.isEnabledFor(logging.DEBUG):
            for count, (path, write_path) in enumerate(write_paths.items(), start=1):
                _logger.debug(
                    "[%0*d/%d]\t%s -> %s",
                    write_paths_width,
                    count,
                    write_paths_len,
                    path,
                    write_path,
                )

    dfs: dict[str, DataFrame] = {}
    for count, path in enumerate(expanded_paths, start=1):
        _logger.info(
            "[%0*d/%d] Reading path as dataframe: %s",
            expanded_paths_width,
            count,
            expanded_paths_len,
            path,
        )

        if not dry_run:
            df = catalog.read_df(path)

            _logger.debug("Dataframe '%s': %s", path, df.cols())
            dfs[path] = df

    cleaned_dfs: dict[str, DataFrame] = {}
    for count, (path, df) in enumerate(dfs.items(), start=1):
        _logger.info(
            "[%0*d/%d] Cleaning dataframe '%s'...",
            width,
            count,
            expanded_paths_len,
            path,
        )

        cleaned_dfs[path] = _clean_df(df)

        write_path = write_paths[path]

        _logger.info(
            "[%0*d/%d] Writing dataframe to '%s'...",
            width,
            count,
            expanded_paths_len,
            write_path,
        )

        if not dry_run:
            catalog.write_df(cleaned_dfs[path], write_path)

    return CleanPathResult()
