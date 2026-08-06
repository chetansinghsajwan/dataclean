from typing import Any

from dataclean.cleaners.cleaner import Cleaner
from dataclean.col_renamer import ColRenamer


class Config:
    ignore_cols: list[str] = []
    cleaners: list[Cleaner] = []
    col_renamer: ColRenamer
    dataframe_apis: list[Any] = []
    inplace: bool = True

    def __init__(
        self,
        col_renamer: ColRenamer,
        ignore_cols: list[str] | None = None,
        cleaners: list[Cleaner] | None = None,
        dataframe_apis: list[Any] | None = None,
        inplace: bool = True,
    ):
        if dataframe_apis is None:
            dataframe_apis = []
        if cleaners is None:
            cleaners = []
        if ignore_cols is None:
            ignore_cols = []
        self.col_renamer = col_renamer
        self.ignore_cols = ignore_cols
        self.cleaners = cleaners
        self.dataframe_apis = dataframe_apis
        self.inplace = inplace


# Global config instance used throughout the package
config = Config(
    col_renamer=ColRenamer(case="snake"),
)


def register_dataframe_api(api: Any) -> None:
    """Register a dataframe API adapter globally.

    Engines should call this at import time to make themselves available to
    consumers without requiring manual registration. Duplicate registrations
    are ignored.
    """
    if api not in config.dataframe_apis:
        config.dataframe_apis.append(api)
