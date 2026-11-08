from pathlib import Path

import pytest

from dataclean.utils.patterns import expand_local_paths, has_glob, is_regex


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in (
        "data/a.csv",
        "data/b.csv",
        "data/report_1.csv",
        "data/report_22.csv",
        "data/sub/c.csv",
        "data/notes.txt",
        "top.csv",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_is_regex_and_has_glob() -> None:
    assert is_regex("re:.*") and not is_regex("data/*.csv")
    assert has_glob("a*") and has_glob("a?") and has_glob("a[1]")
    assert not has_glob("a.csv")


def test_literal_paths_are_returned_unchecked(tree: Path) -> None:
    assert expand_local_paths(["missing.csv", "top.csv", "top.csv"]) == {
        "missing.csv",
        "top.csv",
    }


def test_glob_expands_to_matching_files_only(tree: Path) -> None:
    assert expand_local_paths(["data/*.csv"]) == {
        "data/a.csv",
        "data/b.csv",
        "data/report_1.csv",
        "data/report_22.csv",
    }
    assert expand_local_paths(["data/?.csv"]) == {"data/a.csv", "data/b.csv"}
    assert expand_local_paths(["data/s*"]) == set()  # a directory is not a file


def test_recursive_glob_reaches_every_depth(tree: Path) -> None:
    assert "data/sub/c.csv" in expand_local_paths(["data/**/*.csv"])


def test_glob_without_a_match_gives_nothing(tree: Path) -> None:
    assert expand_local_paths(["data/*.parquet"]) == set()


def test_regex_must_match_the_whole_path(tree: Path) -> None:
    assert expand_local_paths([r"re:data/report_\d+\.csv"]) == {
        "data/report_1.csv",
        "data/report_22.csv",
    }
    assert expand_local_paths([r"re:data/report_\d"]) == set()


def test_regex_without_a_directory_searches_from_the_working_directory(
    tree: Path,
) -> None:
    assert expand_local_paths([r"re:.*\.csv"]) == {
        "top.csv",
        "data/a.csv",
        "data/b.csv",
        "data/report_1.csv",
        "data/report_22.csv",
        "data/sub/c.csv",
    }


def test_regex_alternation_works(tree: Path) -> None:
    assert expand_local_paths(["re:(data/a|top)\\.csv"]) == {"top.csv", "data/a.csv"}


def test_patterns_are_combined_and_deduplicated(tree: Path) -> None:
    assert expand_local_paths(["data/a.csv", "data/?.csv", r"re:data/b\.csv"]) == {
        "data/a.csv",
        "data/b.csv",
    }


def test_invalid_regex_raises_value_error(tree: Path) -> None:
    with pytest.raises(ValueError, match="Invalid regex"):
        expand_local_paths(["re:(unclosed"])
