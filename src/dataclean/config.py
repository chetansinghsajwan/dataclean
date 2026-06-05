from src.dataclean.col_renamer import ColRenamer


class Config:
    ignore_cols: list[str] = []
    cleaners: list[str] = []
    col_renamer: ColRenamer


config = Config(
    col_renamer=ColRenamer(case="snake"),
)
