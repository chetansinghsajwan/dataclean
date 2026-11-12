"""Tests glob and regex expansion of local file paths."""

from pathlib import Path

import pytest

from dataclean.utils.patterns import expand_local_paths, has_glob, is_regex


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Creates a small file tree in a temp directory and works from inside it."""
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
    """Only a re: prefix makes a regex, and only characters like star, question mark
    and brackets make a glob. Plain paths must never be expanded by accident.
    """
    assert is_regex("re:.*") and not is_regex("data/*.csv")
    assert has_glob("a*") and has_glob("a?") and has_glob("a[1]")
    assert not has_glob("a.csv")


def test_literal_paths_are_returned_unchecked(tree: Path) -> None:
    """Paths with no pattern pass straight through, even when the file is missing. The
    later read reports the problem, and naming a file twice counts once.
    """
    assert expand_local_paths(["missing.csv", "top.csv", "top.csv"]) == {
        "missing.csv",
        "top.csv",
    }


def test_glob_expands_to_matching_files_only(tree: Path) -> None:
    """A glob matches files and never folders. Here data/s* would hit the sub folder,
    and we expect nothing back for it.
    """
    assert expand_local_paths(["data/*.csv"]) == {
        "data/a.csv",
        "data/b.csv",
        "data/report_1.csv",
        "data/report_22.csv",
    }
    assert expand_local_paths(["data/?.csv"]) == {"data/a.csv", "data/b.csv"}
    assert expand_local_paths(["data/s*"]) == set()  # a directory is not a file


def test_recursive_glob_reaches_every_depth(tree: Path) -> None:
    """A double star glob goes down into nested folders, so data/sub/c.csv gets found."""
    assert "data/sub/c.csv" in expand_local_paths(["data/**/*.csv"])


def test_glob_without_a_match_gives_nothing(tree: Path) -> None:
    """A glob that matches nothing gives an empty set. It is not an error."""
    assert expand_local_paths(["data/*.parquet"]) == set()


def test_regex_must_match_the_whole_path(tree: Path) -> None:
    """A regex has to match the entire path. A pattern that only covers the start of
    report_1 finds nothing, so stray extra files stay out.
    """
    assert expand_local_paths([r"re:data/report_\d+\.csv"]) == {
        "data/report_1.csv",
        "data/report_22.csv",
    }
    assert expand_local_paths([r"re:data/report_\d"]) == set()


def test_regex_without_a_directory_searches_from_the_working_directory(
    tree: Path,
) -> None:
    """A regex with no folder part is searched from the current directory downwards. It
    finds the file at the top and the ones in every subfolder.
    """
    assert expand_local_paths([r"re:.*\.csv"]) == {
        "top.csv",
        "data/a.csv",
        "data/b.csv",
        "data/report_1.csv",
        "data/report_22.csv",
        "data/sub/c.csv",
    }


def test_regex_alternation_works(tree: Path) -> None:
    """Alternation in a regex, using a pipe, can cover a file inside a folder and one
    at the top. Both come back.
    """
    assert expand_local_paths(["re:(data/a|top)\\.csv"]) == {"top.csv", "data/a.csv"}


def test_patterns_are_combined_and_deduplicated(tree: Path) -> None:
    """A literal name, a glob and a regex that overlap are merged into one set. A file
    named twice is only read once.
    """
    assert expand_local_paths(["data/a.csv", "data/?.csv", r"re:data/b\.csv"]) == {
        "data/a.csv",
        "data/b.csv",
    }


def test_invalid_regex_raises_value_error(tree: Path) -> None:
    """A broken regex raises a clear error. Matching nothing silently would hide the
    typo.
    """
    with pytest.raises(ValueError, match="Invalid regex"):
        expand_local_paths(["re:(unclosed"])
