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
    result = runner.invoke(app, ["a.csv", "b.csv"])
    assert result.exit_code != 0


def test_cli_wires_options_into_clean_paths(monkeypatch: pytest.MonkeyPatch) -> None:
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
            "--cleaners",
            "EmailCleaner",
            "--dry-run",
            "--log",
            "error",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["paths"] == ["in1.csv", "in2.csv"]
    assert captured["write_path"] == "out.csv"
    assert captured["catalog"] == "pandas"
    assert captured["rename_cols"] is False
    assert captured["rename_col_map"] == {"Old Name": "new_name"}
    assert captured["ignore_cols"] == ["country", "email"]
    assert captured["cleaners"] == ["EmailCleaner"]
    assert captured["dry_run"] is True


def test_cli_rejects_malformed_rename_col() -> None:
    result = runner.invoke(
        app, ["clean", "in.csv", "out.csv", "--rename-col", "not-a-mapping"]
    )
    assert result.exit_code != 0


def test_cli_end_to_end_cleans_a_csv(tmp_path) -> None:
    src = tmp_path / "in.csv"
    dest = tmp_path / "out.csv"
    pd.DataFrame({"Client Country": ["IN"]}).to_csv(src, index=False)

    result = runner.invoke(
        app,
        ["clean", str(src), str(dest), "--catalog", "pandas", "--log", "error"],
    )

    assert result.exit_code == 0, result.output
    written = pd.read_csv(dest)
    assert list(written.columns)[1:] == ["client_country"]
    assert written["client_country"].iloc[0] == "India"
