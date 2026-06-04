from logging import Logger, getLogger
from typing import Iterable, Mapping

from src.dataclean.cleaners.base_cleaner import BaseCleaner
from src.dataclean.col_renamer import ColRenamer
from src.dataclean.config import config
from src.dataclean.engine.dataframe import DataFrame


def get_cleaner(df: DataFrame, cols: list[str]) -> (BaseCleaner, float):
    selected_cleaner: BaseCleaner = None
    selected_cleaner_confidence: float = 0

    for cleaner in config.cleaners:
        confidence = cleaner.get_date_type_confidence(df, cols)
        confidence = min(max(confidence, 0), 1)

        if confidence > selected_cleaner_confidence:
            selected_cleaner = cleaner
            selected_cleaner_confidence = confidence

        if confidence == 1:
            break

    return selected_cleaner, selected_cleaner_confidence


def clean_df(
    df: DataFrame,
    rename_cols: bool = True,
    rename_col_map: Mapping[str, str] | None = None,
    col_renamer: ColRenamer | None = ColRenamer(case="snake"),
    clean_cols: bool = True,
    ignore_cols: Iterable[str] | None = None,
    use_global_config: bool = True,
    logger: Logger | None = None,
    cleaners: dict[str, BaseCleaner] | None = None,
) -> DataFrame:

    if logger is None:
        logger = getLogger(__name__)

    logger.debug("Cleaning data...")

    logger.debug(f"df: {df.columns()}")
    logger.debug(f"{rename_cols=}")
    logger.debug(f"{rename_col_map=}")
    logger.debug(f"{col_renamer=}")
    logger.debug(f"{clean_cols=}")
    logger.debug(f"{ignore_cols=}")
    logger.debug(f"{use_global_config=}")

    if ignore_cols is None:
        ignore_cols = None

    if use_global_config:
        logger.debug(f"Global config: {config}")

        ignore_cols = list(set(ignore_cols + config.ignore_cols))

    if rename_cols:
        if rename_col_map is None:
            rename_col_map = col_renamer.generate_rename_map(df.columns())
        else:
            cols_to_auto_rename = [
                col for col in df.columns() if col not in rename_col_map
            ]
            auto_rename_col_map = col_renamer.generate_rename_map(cols_to_auto_rename)

            logger.debug(f"Rename map from the column renamer: {auto_rename_col_map}")

            rename_col_map = auto_rename_col_map | rename_col_map

        logger.info(f"Renaming columns using map: {rename_col_map}")

        df.rename_cols(rename_col_map)

    if clean_cols:
        auto_clean_columns = [col for col in df.columns() if col not in cleaners]
        col_cleaner_map = dict()

        for col in auto_clean_columns:
            logger.debug(f"Finding cleaner for col '{col}'")
            cleaner, cleaner_confidence = get_cleaner(df, (col))

            logger.debug(
                f"Found cleaner '{cleaner.name()}' for '{col}' with confidence '{cleaner_confidence}'"
            )

            col_cleaner_map[col] = cleaner

        df.add_columns({col: cleaner.clean_value for col in col_cleaner_map})

    return df
