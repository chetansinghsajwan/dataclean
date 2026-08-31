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
    if catalog is None:
        return "None"

    if isinstance(catalog, type):
        return catalog.__name__

    return catalog.__class__.__name__


def clean(df, auto_detect: bool = True):
    """
    Clean a dataframe with automatic cleaner detection.

    Args:
        df: DataFrame to clean (pandas, pyspark, or DataFrame-compatible).
        auto_detect: If True, auto-detect cleaners for columns.
        catalog: Catalog to use for cleaner registration (defaults to DefaultCatalog).

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
