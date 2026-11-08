import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import FilePathCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver


def _clean(value: str, **kwargs: object) -> str | None:
    return FilePathCleaner(**kwargs).clean_row(value)  # type: ignore[arg-type]


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
    assert _clean(raw) == expected


def test_file_path_cleaner_keeps_the_case_of_the_name() -> None:
    assert _clean("Report.PDF") == "Report.pdf"


def test_file_path_cleaner_keeps_a_network_share_prefix() -> None:
    assert _clean("\\\\server\\share\\a.TXT") == "//server/share/a.txt"


def test_file_path_cleaner_does_not_treat_long_or_spaced_suffixes_as_extensions() -> (
    None
):
    assert _clean("Mr. SMITH") == "Mr. SMITH"
    assert _clean("notes.ABCDEFGHIJKL") == "notes.ABCDEFGHIJKL"


# ==============================================================================
# 2. OPTIONS
# ==============================================================================


def test_file_path_cleaner_separator_is_configurable() -> None:
    assert _clean("C:/a//b/c.TXT", separator="\\") == "C:\\a\\b\\c.txt"


def test_file_path_cleaner_can_keep_the_extension_case() -> None:
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
    assert _clean(raw) is None


# ==============================================================================
# 4. DETECTION AND PIPELINE
# ==============================================================================


@pytest.mark.parametrize(
    "name",
    ["filename", "file_name", "FilePath", "path", "dirname", "upload_dir", "folder"],
)
def test_file_path_cleaner_claims_file_like_column_names(name: str) -> None:
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert FilePathCleaner().match_score(df, (name,)) == 1.0


@pytest.mark.parametrize(
    "name", ["url_path", "file_id", "colname", "username", "profile", "name"]
)
def test_file_path_cleaner_ignores_other_column_names(name: str) -> None:
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert FilePathCleaner().match_score(df, (name,)) == 0.0


def test_resolver_assigns_file_path_cleaner_to_each_file_column() -> None:
    cols = {"filename", "path", "colname"}
    df = PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))

    assignments = Resolver(cleaners=(FilePathCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {"filename", "path"}


def test_pipeline_cleans_file_column_in_place() -> None:
    df = PandasDataFrame(
        df=pd.DataFrame({"filename": ["IMG_01.PNG", "a|b", None, "  "]})
    )

    cleaned = Pipeline(cleaners=(FilePathCleaner(),)).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["filename"].tolist() == ["IMG_01.png", None, None, None]
