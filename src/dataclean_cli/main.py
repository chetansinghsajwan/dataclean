from typing import Annotated

import typer

import dataclean

from . import logs

app = typer.Typer()


@app.callback()
def _callback() -> None:
    """dataclean: automatic data cleaning."""


def parse_mapping(value: str) -> tuple[str, str]:
    try:
        key, value = value.split("=", 1)
    except ValueError as e:
        raise typer.BadParameter("Expected KEY=VALUE") from e

    return key, value


@app.command()
def clean(
    paths: Annotated[
        list[str],
        typer.Argument(
            help="Path pattern(s) to expand via the catalog (e.g. glob-style wildcards)."
        ),
    ],
    write_path: Annotated[
        str,
        typer.Argument(
            help="Template path each expanded path is mapped onto for writing the cleaned result."
        ),
    ],
    catalog: Annotated[
        str | None,
        typer.Option(
            help=(
                "Name of the catalog to use (e.g. 'pandas'). If not given, "
                "resolved from the environment."
            )
        ),
    ] = None,
    clean_cols: Annotated[
        bool,
        typer.Option(help="Whether to clean column values via the cleaning pipeline."),
    ] = True,
    auto_rename_cols: Annotated[
        bool, typer.Option(help="Whether to auto-rename columns to a consistent case.")
    ] = True,
    rename_col: Annotated[
        list[str] | None,
        typer.Option(
            help="Explicit column rename(s), as OLD_NAME=NEW_NAME. Repeatable."
        ),
    ] = None,
    ignore_col: Annotated[
        list[str] | None,
        typer.Option(help="Column(s) to exclude from cleaning. Repeatable."),
    ] = None,
    inplace: Annotated[
        bool | None, typer.Option(help="Whether to clean dataframes in place.")
    ] = None,
    cleaners: Annotated[
        list[str] | None,
        typer.Option(
            help="Restrict cleaning to these cleaner name(s) (e.g. 'EmailCleaner'). Repeatable."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            help="Expand and map paths, but skip reading, cleaning, and writing."
        ),
    ] = False,
    log: Annotated[
        logs.LevelNames, typer.Option(help="Log level.")
    ] = logs.defaultLevel,
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
