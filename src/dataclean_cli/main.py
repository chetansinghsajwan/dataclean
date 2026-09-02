import typer

app = typer.Typer()


def parse_mapping(value: str) -> tuple[str, str]:
    try:
        key, value = value.split("=", 1)
    except ValueError as e:
        raise typer.BadParameter("Expected KEY=VALUE") from e

    return key, value


@app.command()
def clean(
    paths: list[str],
    write_path: str | None = None,
    catalog: str | None = None,
    clean_cols: bool = True,
    auto_rename_cols: bool = True,
    rename_col: list[str] | None = None,
    ignore_col: list[str] | None = None,
    inplace: bool | None = None,
    cleaners: list[str] | None = None,
    dry_run: bool = False,
):
    """Clean the data."""

    # use_global_config: bool = True
    # parsed_rename_col_map = (
    #     dict(parse_mapping(x) for x in rename_col) if rename_col else {}
    # )

    pass


def main():
    app()


if __name__ == "__main__":
    main()
