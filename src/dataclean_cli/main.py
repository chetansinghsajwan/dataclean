import typer

import dataclean

from . import logs

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
    write_path: str,
    catalog: str | None = None,
    clean_cols: bool = True,
    auto_rename_cols: bool = True,
    rename_col: list[str] | None = None,
    ignore_col: list[str] | None = None,
    inplace: bool | None = None,
    cleaners: list[str] | None = None,
    dry_run: bool = False,
    log: logs.LevelNames = logs.defaultLevel,
):
    """Clean the data."""

    logs.setup_logging(log)

    use_global_config: bool = True
    parsed_rename_col_map = (
        dict(parse_mapping(x) for x in rename_col) if rename_col else {}
    )

    dataclean.clean_paths(
        paths=paths,
        write_path=write_path,
        catalog=catalog,
        clean_cols=clean_cols,
        rename_cols=auto_rename_cols,
        rename_col_map=parsed_rename_col_map,
        ignore_cols=ignore_col,
        inplace=inplace,
        use_global_config=use_global_config,
        cleaners=cleaners,
        dry_run=dry_run,
    )


def main():
    app()


if __name__ == "__main__":
    main()
