"""Tests for incremental SCD 2 cleaning through clean_paths."""

from pathlib import Path

import pandas as pd
import pytest

from dataclean import Scd2, clean_paths

SCD = Scd2(key_cols=("id",))


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _run(src: Path, out: Path) -> pd.DataFrame:
    clean_paths([str(src)], write_path=str(out), catalog="pandas", scd=SCD)
    return pd.read_csv(out)


def _row(id_: int, email: str, active: bool, to: str | None, frm: str = "2024-01-01"):
    return {
        "id": id_,
        "email": email,
        "scd_active": active,
        "scd_from": frm,
        "scd_to": to,
    }


def test_first_run_cleans_every_version(tmp_path: Path) -> None:
    """With no earlier output there is nothing to skip, so every version, current or closed, is cleaned."""
    src, out = tmp_path / "in.csv", tmp_path / "out.csv"
    _write(
        src,
        [_row(1, " A@X.COM ", True, None), _row(2, " B@X.COM ", False, "2024-02-01")],
    )
    result = _run(src, out)
    assert sorted(result["email"]) == ["a@x.com", "b@x.com"]


def test_rerun_cleans_only_new_versions_and_keeps_history(tmp_path: Path) -> None:
    """A new version arrives and the old one closes. Only the new row and the closed row are cleaned again, the output keeps both, and the untouched record stays as it was."""
    src, out = tmp_path / "in.csv", tmp_path / "out.csv"
    _write(src, [_row(1, " A@X.COM ", True, None), _row(2, " B@X.COM ", True, None)])
    _run(src, out)

    _write(
        src,
        [
            _row(1, " A@X.COM ", False, "2024-03-01"),
            _row(1, " NEW@X.COM ", True, None, frm="2024-03-01"),
            _row(2, " B@X.COM ", True, None),
        ],
    )
    result = _run(src, out).sort_values(["id", "scd_from"]).reset_index(drop=True)

    assert list(result["email"]) == ["a@x.com", "new@x.com", "b@x.com"]
    assert list(result["scd_active"]) == [False, True, True]
    assert result.loc[0, "scd_to"] == "2024-03-01"


def test_rerun_with_no_changes_leaves_output_untouched(tmp_path: Path) -> None:
    """When the source has no new or closed versions the output is not rewritten."""
    src, out = tmp_path / "in.csv", tmp_path / "out.csv"
    _write(src, [_row(1, " A@X.COM ", True, None)])
    _run(src, out)
    before = out.stat().st_mtime_ns
    _run(src, out)
    assert out.stat().st_mtime_ns == before


def test_scd_columns_and_keys_are_not_cleaned(tmp_path: Path) -> None:
    """The keys and history columns are what source and output are matched on, so cleaning must not change them."""
    src, out = tmp_path / "in.csv", tmp_path / "out.csv"
    _write(src, [_row(1, "a@x.com", True, None, frm="2024-01-01 00:00:00")])
    result = _run(src, out)
    assert result.loc[0, "scd_from"] == "2024-01-01 00:00:00"
    assert result.loc[0, "scd_active"]


def test_missing_scd_column_is_an_error(tmp_path: Path) -> None:
    """A source without the named history columns fails clearly instead of cleaning wrongly."""
    src, out = tmp_path / "in.csv", tmp_path / "out.csv"
    pd.DataFrame({"id": [1], "email": ["a@x.com"]}).to_csv(src, index=False)
    with pytest.raises(ValueError, match="missing SCD columns"):
        _run(src, out)


def test_scd2_needs_a_key() -> None:
    """Without a key there is no way to tell versions of the same record apart."""
    with pytest.raises(ValueError):
        Scd2(key_cols=())
