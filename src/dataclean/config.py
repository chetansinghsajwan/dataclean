from dataclean.col_renamer import ColRenamer
from dataclean.engine.dataframe import DataFrame


class Config:
    ignore_cols: list[str] = []
    cleaners: list[str] = []
    col_renamer: ColRenamer
    dataframe_apis: list[DataFrame]
    inplace: bool

    def __init__(
        self,
        col_renamer: ColRenamer,
        ignore_cols: list[str] = [],
        cleaners: list[str] = [],
        dataframe_apis: list[DataFrame] = [],
        inplace: bool = True,
    ):
        self.col_renamer = col_renamer
        self.ignore_cols = ignore_cols
        self.cleaners = cleaners
        self.dataframe_apis = dataframe_apis
        self.inplace = inplace


config = Config(
    col_renamer=ColRenamer(case="snake"),
)
