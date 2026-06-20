from logging import Logger, getLogger
from typing import Any, Iterable, Mapping

from dataclean.cleaners.base_cleaner import BaseCleaner
from dataclean.col_renamer import ColRenamer
from dataclean.config import config
from dataclean.engine.dataframe import DataFrame, DataWriter
from dataclean.types import strict_validate


def get_cleaner(df: DataFrame, cols: Iterable[str]) -> (BaseCleaner, float):
    selected_cleaner: BaseCleaner = None
    selected_cleaner_confidence: float = 0

    for cleaner in config.cleaners:
        confidence = cleaner.get_data_type_confidence(df, cols)
        confidence = min(max(confidence, 0), 1)

        if confidence > selected_cleaner_confidence:
            selected_cleaner = cleaner
            selected_cleaner_confidence = confidence

        if confidence == 1:
            break

    return selected_cleaner, selected_cleaner_confidence


def _wrap_df(df: Any) -> DataFrame:

    if isinstance(df, DataFrame):
        return df

    for api in config.dataframe_apis:
        if api.supports(df):
            return api(df=df)

    return None


@strict_validate
def clean(
    df: DataFrame | Any,
    rename_cols: bool = True,
    rename_col_map: Mapping[str, str] | None = None,
    col_renamer: ColRenamer | None = ColRenamer(case="snake"),
    clean_cols: bool = True,
    ignore_cols: Iterable[str] | None = None,
    use_global_config: bool = True,
    logger: Logger | None = None,
    inplace: bool | None = None,
    cleaners: dict[str, BaseCleaner] | None = None,
) -> DataFrame:

    if logger is None:
        logger = getLogger(__name__)

    wrapped_df = _wrap_df(df)
    if wrapped_df is None:
        e = TypeError(
            f"Dataframe of type '{type(df)}' is not supported. Register your dataframe."
        )
        logger.error(e)

        raise e

    df = wrapped_df

    logger.debug("Cleaning data...")

    logger.debug(f"df: {df.cols()}")
    logger.debug(f"{rename_cols=}")
    logger.debug(f"{rename_col_map=}")
    logger.debug(f"{col_renamer=}")
    logger.debug(f"{clean_cols=}")
    logger.debug(f"{ignore_cols=}, {config.ignore_cols=}")
    logger.debug(f"{inplace=}, {config.inplace=}")
    logger.debug(f"{use_global_config=}")

    if ignore_cols is None:
        ignore_cols = list()

    if inplace is None:
        inplace = config.inplace

    if cleaners is None:
        cleaners = list()

    if use_global_config:
        logger.debug(f"Global config: {config}")

        ignore_cols = list(set(ignore_cols + config.ignore_cols))

    if rename_cols:
        if rename_col_map is None:
            rename_col_map = col_renamer.rename_cols(df.col_names())
        else:
            cols_to_auto_rename = [
                col for col in df.col_names() if col not in rename_col_map
            ]
            auto_rename_col_map = col_renamer.rename_cols(cols_to_auto_rename)

            logger.debug(f"Rename map from the column renamer: {auto_rename_col_map}")

            rename_col_map = auto_rename_col_map | rename_col_map

        logger.info(f"Renaming columns using map: {rename_col_map}")

        df.rename_cols(rename_col_map)

    if clean_cols:
        auto_clean_cols = [col for col in df.col_names() if col not in cleaners]
        col_cleaner_map: dict[str, BaseCleaner] = dict()

        for col in auto_clean_cols:
            logger.debug(f"Finding cleaner for col '{col}'")
            cleaner, cleaner_confidence = get_cleaner(df, (col,))

            if cleaner is None:
                logger.warning(f"No cleaner found for col '{col}'")
                continue

            logger.debug(
                f"Found cleaner '{cleaner.name()}' for '{col}' with confidence '{cleaner_confidence}'"
            )

            col_cleaner_map[col] = cleaner

        writers = list()
        for col, cleaner in col_cleaner_map.items():
            schema = cleaner.output_schema()

            if not isinstance(schema, tuple):
                writers.append(
                    DataWriter(
                        expr=cleaner.clean_value,
                        read_cols=(col,),
                        write_cols=((f"{col}_cleaned", schema),),
                    )
                )
                continue

            writers.append(
                DataWriter(
                    expr=cleaner.clean_value,
                    read_cols=(col,),
                    write_cols=tuple(
                        (f"{col}_{comp}_cleaned", data_type)
                        for comp, data_type in schema
                    ),
                )
            )

        df.write_cols(writers)

    return df
