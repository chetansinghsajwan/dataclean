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
        ignore_cols: list[str] = None,
        cleaners: list[str] = None,
        dataframe_apis: list[DataFrame] = None,
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


config = Config(
    col_renamer=ColRenamer(case="snake"),
)
