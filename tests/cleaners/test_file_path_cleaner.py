"""Tests for FilePathCleaner: path normalisation, options, invalid values and pipeline use."""

from typing import Any

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import FilePathCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver


def _clean(value: str, **kwargs: Any) -> str | None:
    return FilePathCleaner(**kwargs).clean_row(value)


# ==============================================================================
# 1. NORMALIZATION
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("report.pdf", "report.pdf"),
        ("IMG_01.PNG", "IMG_01.png"),
        ("archive.tar.GZ", "archive.tar.gz"),
        ("  report.pdf  ", "report.pdf"),
        ('"C:\\Users\\Ann\\Report.DOCX"', "C:/Users/Ann/Report.docx"),
        ("'/home/ann/notes.TXT'", "/home/ann/notes.txt"),
        ("\u200b/tmp/a.txt", "/tmp/a.txt"),
        ("/home//ann///a.txt", "/home/ann/a.txt"),
        ("/home/./ann/./a.txt", "/home/ann/a.txt"),
        ("dir\\sub\\a.txt", "dir/sub/a.txt"),
        ("../up/a.txt", "../up/a.txt"),
        ("My Report  v2.pdf", "My Report  v2.pdf"),
        (".bashrc", ".bashrc"),
        ("README", "README"),
        ("/var/log/", "/var/log/"),
    ],
)
def test_file_path_cleaner_normalizes_separators_noise_and_extension(
    raw: str, expected: str
) -> None:
    """Paths arrive with stray quotes, spaces, doubled slashes, backslashes and shouty
    extensions. We tidy all of that so the same file always ends up with one
    spelling."""
    assert _clean(raw) == expected


def test_file_path_cleaner_keeps_the_case_of_the_name() -> None:
    """Only the extension is lowercased. The file name itself may be case-sensitive on
    disk, so we leave it exactly as written."""
    assert _clean("Report.PDF") == "Report.pdf"


def test_file_path_cleaner_keeps_a_network_share_prefix() -> None:
    """A path starting with two backslashes points at a network share. We turn the
    slashes around but keep the double slash at the front, since dropping it would
    change where the path leads."""
    assert _clean("\\\\server\\share\\a.TXT") == "//server/share/a.txt"


def test_file_path_cleaner_does_not_treat_long_or_spaced_suffixes_as_extensions() -> (
    None
):
    """Not every dot starts an extension. In Mr. SMITH or a very long suffix the text
    after the dot is part of the name, so we don't lowercase it."""
    assert _clean("Mr. SMITH") == "Mr. SMITH"
    assert _clean("notes.ABCDEFGHIJKL") == "notes.ABCDEFGHIJKL"


# ==============================================================================
# 2. OPTIONS
# ==============================================================================


def test_file_path_cleaner_separator_is_configurable() -> None:
    """Not everyone wants forward slashes. If asked for a backslash, the output should
    use it throughout, and still tidy the doubled slashes."""
    assert _clean("C:/a//b/c.TXT", separator="\\") == "C:\\a\\b\\c.txt"


def test_file_path_cleaner_can_keep_the_extension_case() -> None:
    """Lowercasing the extension is the default, but some people need the original
    case. Turning the option off leaves it alone."""
    assert _clean("IMG.PNG", lowercase_extension=False) == "IMG.PNG"


# ==============================================================================
# 3. INVALID VALUES
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "a<b.txt",
        'a"b.txt',
        "a|b.txt",
        "what?.txt",
        "*.txt",
        "bad\x00name.txt",
        "bad\tname.txt",
        "<script>alert(1)</script>",
        "file:///tmp/a.txt",
        "a:b.txt",
        ".",
        "..",
        "./",
        "/",
        "///",
        "C:",
    ],
)
def test_file_path_cleaner_nulls_values_that_cannot_name_a_file(raw: str) -> None:
    """Characters like angle brackets, pipes, question marks and control characters
    can't appear in a file name, and neither can URLs or bare dots and slashes.
    Those values can't name a file, so they become null."""
    assert _clean(raw) is None


# ==============================================================================
# 4. DETECTION AND PIPELINE
# ==============================================================================


@pytest.mark.parametrize(
    "name",
    ["filename", "file_name", "FilePath", "path", "dirname", "upload_dir", "folder"],
)
def test_file_path_cleaner_claims_file_like_column_names(name: str) -> None:
    """Columns called filename, path, folder and the like are almost certainly paths.
    The cleaner should say it is fully confident about them."""
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert FilePathCleaner().match_score(df, (name,)) == 1.0


@pytest.mark.parametrize(
    "name", ["url_path", "file_id", "colname", "username", "profile", "name"]
)
def test_file_path_cleaner_ignores_other_column_names(name: str) -> None:
    """Names that only look similar, such as url_path, file_id or username, hold
    something else. The cleaner should score them zero and stay out of the way."""
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert FilePathCleaner().match_score(df, (name,)) == 0.0


def test_resolver_assigns_file_path_cleaner_to_each_file_column() -> None:
    """When the resolver sees a table with filename, path and an unrelated colname
    column, it should hand the first two to this cleaner and leave the third alone."""
    cols = {"filename", "path", "colname"}
    df = PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))

    assignments = Resolver(cleaners=(FilePathCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {"filename", "path"}


def test_pipeline_cleans_file_column_in_place() -> None:
    """This runs the cleaner end to end in a pipeline. The filename column is cleaned
    where it sits, with the bad value, the missing one and the blank one all turning
    into null."""
    df = PandasDataFrame(
        df=pd.DataFrame({"filename": ["IMG_01.PNG", "a|b", None, "  "]})
    )

    cleaned = Pipeline(cleaners=(FilePathCleaner(),)).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["filename"].tolist() == ["IMG_01.png", None, None, None]
