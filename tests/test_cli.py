"""Tests for the dataclean command line interface."""

from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

from dataclean_cli.main import app

runner = CliRunner()


def test_cli_requires_the_clean_subcommand_name() -> None:
    # A Typer app with a single command collapses to that command by
    # default; the app's callback (see main.py) exists specifically to keep
    # "clean" a required subcommand name rather than implicit.
    """A Typer app with a single command normally lets you skip the command name. We want clean to be spelled out, so that adding other commands later never changes how people call it today."""
    result = runner.invoke(app, ["a.csv", "b.csv"])
    assert result.exit_code != 0


def test_cli_wires_options_into_clean_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command line is only a thin layer over clean_paths. We replace that function with a stand-in, pass every flag, and check each one arrives under the right argument name."""
    captured: dict[str, Any] = {}

    def fake_clean_paths(**kwargs: Any):
        captured.update(kwargs)

    import dataclean_cli.main as main_module

    monkeypatch.setattr(main_module.dataclean, "clean_paths", fake_clean_paths)

    result = runner.invoke(
        app,
        [
            "clean",
            "in1.csv",
            "in2.csv",
            "out.csv",
            "--catalog",
            "pandas",
            "--no-auto-rename-cols",
            "--rename-col",
            "Old Name=new_name",
            "--ignore-col",
            "country",
            "--ignore-col",
            "email",
            "--col",
            "contact=EmailCleaner",
            "--cleaners",
            "EmailCleaner",
            "--dry-run",
            "--keep-original",
            "--original-suffix",
            "_raw",
            "--log",
            "error",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["keep_original"] is True
    assert captured["original_suffix"] == "_raw"
    assert captured["paths"] == ["in1.csv", "in2.csv"]
    assert captured["write_path"] == "out.csv"
    assert captured["catalog"] == "pandas"
    assert captured["rename_cols"] is False
    assert captured["rename_col_map"] == {"Old Name": "new_name"}
    assert captured["ignore_cols"] == ["country", "email"]
    assert captured["cleaners"] == ["EmailCleaner"]
    assert captured["column_cleaners"] == {"contact": "EmailCleaner"}
    assert captured["dry_run"] is True


def test_cli_rejects_malformed_rename_col() -> None:
    """A rename given without an equals sign cannot be understood. The command should fail rather than guess what was meant."""
    result = runner.invoke(
        app, ["clean", "in.csv", "out.csv", "--rename-col", "not-a-mapping"]
    )
    assert result.exit_code != 0


def test_cli_end_to_end_cleans_a_csv(tmp_path) -> None:
    """A full run on a real CSV file. The column gets renamed to client_country and the value IN is cleaned to India, which shows the whole chain works."""
    src = tmp_path / "in.csv"
    dest = tmp_path / "out.csv"
    pd.DataFrame({"Client Country": ["IN"]}).to_csv(src, index=False)

    result = runner.invoke(
        app,
        ["clean", str(src), str(dest), "--catalog", "pandas", "--log", "error"],
    )

    assert result.exit_code == 0, result.output
    written = pd.read_csv(dest)
    assert list(written.columns) == ["client_country"]
    assert written["client_country"].iloc[0] == "India"


def test_cli_rejects_malformed_col() -> None:
    """The same goes for the column cleaner option. Something that is not in column=cleaner form is a mistake, so the command fails."""
    result = runner.invoke(
        app, ["clean", "in.csv", "out.csv", "--col", "not-a-mapping"]
    )
    assert result.exit_code != 0


def test_cli_col_overrides_detection_end_to_end(tmp_path) -> None:
    """A real CSV with a column called contact, which we cannot recognise by name. Telling the CLI to use the email cleaner for it gives a lowercased, trimmed address in the output file."""
    src = tmp_path / "in.csv"
    dest = tmp_path / "out.csv"
    pd.DataFrame({"contact": [" Bob@Example.COM "]}).to_csv(src, index=False)

    result = runner.invoke(
        app,
        [
            "clean",
            str(src),
            str(dest),
            "--catalog",
            "pandas",
            "--col",
            "contact=EmailCleaner",
        ],
    )

    assert result.exit_code == 0, result.output
    assert pd.read_csv(dest)["contact"].iloc[0] == "bob@example.com"
