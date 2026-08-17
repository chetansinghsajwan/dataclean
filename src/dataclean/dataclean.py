from collections.abc import Iterable, Mapping
from typing import Any

from dataclean.logs.log_level import LogLevel

from .cleaners.cleaner import Cleaner
from .col_renamer import ColRenamer
from .config import config
from .engine.dataframe import DataFrame, DataWriter
from .types import checked
from .utils import _log_args


def get_cleaner(df: DataFrame, cols: Iterable[str]) -> tuple[Cleaner | None, float]:
    selected_cleaner: Cleaner | None = None
    selected_cleaner_confidence: float = 0

    for cleaner in config.cleaners:
        # Ensure we pass a tuple to older cleaners expecting tuple semantics
        confidence = cleaner.match_score(df, tuple(cols))
        confidence = min(max(confidence, 0.0), 1.0)

        if confidence > selected_cleaner_confidence:
            selected_cleaner = cleaner
            selected_cleaner_confidence = confidence

        if confidence == 1:
            break

    return selected_cleaner, selected_cleaner_confidence


def _wrap_df(df: Any) -> DataFrame | None:

    if isinstance(df, DataFrame):
        return df

    for api in config.dataframe_apis:
        if api.supports(df):
            return api(df=df)

    return None


@checked
def clean(
    df: DataFrame | Any,
    rename_cols: bool = True,
    rename_col_map: Mapping[str, str] | None = None,
    col_renamer: ColRenamer | None = None,
    clean_cols: bool = True,
    ignore_cols: Iterable[str] | None = None,
    use_global_config: bool = True,
    inplace: bool | None = None,
    cleaners: Iterable[str] | None = None,
) -> DataFrame:

    logger = config.get_logger(__name__)
    col_renamer = col_renamer or config.col_renamer

    wrapped_df = _wrap_df(df)
    if wrapped_df is None:
        e = TypeError(
            f"Dataframe of type '{type(df)}' is not supported. Register your dataframe."
        )
        logger.error(e)
        raise e

    df = wrapped_df

    _log_args(
        logger,
        LogLevel.DEBUG,
        df=df,
        rename_cols=rename_cols,
        rename_col_map=rename_col_map,
        col_renamer=col_renamer,
        clean_cols=clean_cols,
        ignore_cols=ignore_cols,
        inplace=inplace,
        use_global_config=use_global_config,
        cleaners=cleaners,
    )

    logger.debug("Cleaning data...")

    if ignore_cols is None:
        ignore_cols = []

    if inplace is None:
        inplace = config.inplace

    if cleaners is None:
        cleaners = []  # expected to be an iterable of column names to skip

    if use_global_config:
        logger.debug(f"Global config: {config}")
        # Normalize both iterables to tuples before concatenation to satisfy type checker
        ignore_cols = list(set(tuple(ignore_cols) + tuple(config.ignore_cols)))

    if rename_cols:
        if rename_col_map is None:
            rename_col_map = col_renamer.rename_cols(list(df.col_names()))
        else:
            cols_to_auto_rename = [
                col for col in df.col_names() if col not in rename_col_map
            ]
            auto_rename_col_map = col_renamer.rename_cols(cols_to_auto_rename)
            logger.debug(f"Rename map from the column renamer: {auto_rename_col_map}")
            # Normalize mapping types to dict before merging
            rename_col_map = dict(auto_rename_col_map) | dict(rename_col_map)

        logger.info(f"Renaming columns using map: {rename_col_map}")

        df.rename_cols(rename_col_map)

    if clean_cols:
        auto_clean_cols = [col for col in df.col_names() if col not in cleaners]
        col_cleaner_map: dict[str, Cleaner] = {}

        for col in auto_clean_cols:
            logger.debug(f"Finding cleaner for col '{col}'")
            cleaner, cleaner_confidence = get_cleaner(df, (col,))

            if cleaner is None:
                logger.warning(f"No cleaner found for col '{col}'")
                continue

            logger.debug(
                f"Found cleaner '{cleaner.name}' for '{col}' with confidence '{cleaner_confidence}'"
            )

            col_cleaner_map[col] = cleaner

        writers = []
        for col, cleaner in col_cleaner_map.items():
            outputs = cleaner.outputs
            cols = outputs.cols if outputs is not None else ()

            # Single-column output (default)
            if len(cols) == 1:
                dtype = cols[0].dtype
                writers.append(
                    DataWriter(
                        expr=cleaner.clean_row,
                        read_cols=(col,),
                        write_cols=((f"{col}_cleaned", dtype),),
                    )
                )
                continue

            # Multi-column outputs
            write_cols = []
            for i, outcol in enumerate(cols):
                name = outcol.name or f"{col}_{i}"
                write_cols.append((f"{col}_{name}_cleaned", outcol.dtype))

            writers.append(
                DataWriter(
                    expr=cleaner.clean_row,
                    read_cols=(col,),
                    write_cols=tuple(write_cols),
                )
            )

        df.write_cols(writers)

    return df
