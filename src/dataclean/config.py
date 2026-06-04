from src.dataclean.col_renamer import ColRenamer


class Config:
    ignore_cols: list[str] = []
    cleaners: list[str] = []
    col_renamer: ColRenamer

    def __init__(
        self,
        col_renamer: ColRenamer,
        ignore_cols: list[str] = [],
        cleaners: list[str] = [],
    ):
        self.col_renamer = col_renamer
        self.ignore_cols = ignore_cols
        self.cleaners = cleaners


config = Config(
    col_renamer=ColRenamer(case="snake"),
)
