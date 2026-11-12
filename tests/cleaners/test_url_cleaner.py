"""URL cleaner tests: normalising, default scheme, rejecting non-web values, multiple URLs, output format and detection."""

from typing import Any

import pandas as pd
import pytest
from dataclean_pandas import PandasDataFrame

from dataclean import UrlCleaner
from dataclean.pipeline import Pipeline
from dataclean.pipeline.cleaner_resolver import Resolver


def _clean(value: str, **kwargs: Any) -> str | None:
    return UrlCleaner(**kwargs).clean_row(value)


# ==============================================================================
# 1. NORMALIZATION
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("http://www.bcbgroup.io/", "http://www.bcbgroup.io"),
        ("HTTPS://WWW.Example.COM/Path/Page", "https://www.example.com/Path/Page"),
        ("  https://example.com  ", "https://example.com"),
        ("<https://example.com>", "https://example.com"),
        ('"https://example.com"', "https://example.com"),
        ("​https://example.com", "https://example.com"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("http://example.com:80", "http://example.com"),
        ("http://example.com:8080/a", "http://example.com:8080/a"),
        ("https://example.com.", "https://example.com"),
        ("https://example.com/?a=1", "https://example.com/?a=1"),
        ("https://example.com/a?B=2#Top", "https://example.com/a?B=2#Top"),
        ("https://example.com/a/", "https://example.com/a/"),
    ],
)
def test_url_cleaner_normalizes_scheme_host_port_and_bare_slash(
    raw: str, expected: str
) -> None:
    """Many spellings of the same site go in, with different casing, default ports or a lone trailing slash. They should all come out in one tidy form, which makes duplicates easy to spot."""
    assert _clean(raw) == expected


def test_url_cleaner_keeps_www_and_http() -> None:
    """We leave www and plain http alone. Removing them could point to a different site, so tidying stops short of that."""
    assert _clean("http://www.example.com") == "http://www.example.com"


# ==============================================================================
# 2. MISSING SCHEME
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("www.example.com", "https://www.example.com"),
        ("example.com/a", "https://example.com/a"),
        ("//example.com", "https://example.com"),
        ("example.com:8080/a", "https://example.com:8080/a"),
    ],
)
def test_url_cleaner_adds_default_scheme(raw: str, expected: str) -> None:
    """A bare value like example.com in a URL column is meant as a web address. We add https in front so it becomes a proper link."""
    assert _clean(raw) == expected


def test_url_cleaner_default_scheme_is_configurable() -> None:
    """Not every site supports https. A user can choose http as the scheme added to bare domains."""
    assert _clean("example.com", default_scheme="http") == "http://example.com"


# ==============================================================================
# 3. INVALID VALUES
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "n/a",
        "abc",
        "http://",
        "https://localhost",
        "javascript:alert(1)",
        "mailto:a@b.com",
        "ftp://example.com",
        "http://exa mple.com",
        "https://example.com/a b",
        "http://-bad-.com",
        "http://example.123",
        "http://exa_mple..com",
        "<script>alert(1)</script>",
        "{{7*7}}",
        "%s%s%s%n",
        "../../etc/passwd",
        "http://[::zz]/",
        "http://example.com:99999",
    ],
)
def test_url_cleaner_nulls_values_that_are_not_web_urls(raw: str) -> None:
    """This list covers the junk that ends up in URL columns, such as other schemes, bad hostnames, script snippets and file paths. None of it is a web address, so each becomes null."""
    assert _clean(raw) is None


def test_url_cleaner_accepts_ip_hosts() -> None:
    """Web addresses can use an IP instead of a name. Both IPv4 and IPv6 hosts are kept, along with the port and path."""
    assert _clean("http://192.168.0.1:8080/x") == "http://192.168.0.1:8080/x"
    assert _clean("http://[2001:db8::1]/x") == "http://[2001:db8::1]/x"


def test_url_cleaner_keeps_internationalized_hosts_in_unicode() -> None:
    """Hosts written with non-English letters are kept readable and lowercased, not turned into the xn-- form. That is what people expect to see in a report."""
    assert _clean("https://BÜCHER.example/") == "https://bücher.example"
    assert _clean("http://例え.jp") == "http://例え.jp"


# ==============================================================================
# 4. SEVERAL URLS
# ==============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "http://a.com; http://b.com",
        "http://a.com | http://b.com",
        "http://a.com, http://b.com",
        "http://a.com or http://b.com",
        "n/a; http://a.com",
    ],
)
def test_url_cleaner_keeps_the_first_valid_url(raw: str) -> None:
    """One cell sometimes lists several URLs separated by semicolons, pipes, commas or the word or. We keep the first valid one, skipping any junk in front of it."""
    assert _clean(raw) == "http://a.com"


def test_url_cleaner_keeps_a_comma_inside_a_path() -> None:
    """A comma can be a genuine part of a path. It should not be mistaken for a separator between two URLs."""
    assert _clean("http://a.com/x,y") == "http://a.com/x,y"


# ==============================================================================
# 5. OUTPUT FORMAT
# ==============================================================================


def test_url_cleaner_domain_format_returns_the_host_only() -> None:
    """In domain mode only the lowercased host comes back, so the scheme, port, path and query are all dropped. Text that is not a URL still gives null."""
    cleaner = UrlCleaner(out_format=UrlCleaner.Format.DOMAIN)

    assert cleaner.clean_row("HTTP://WWW.Example.com:8080/a?b=1") == "www.example.com"
    assert cleaner.clean_row("junk") is None


# ==============================================================================
# 6. DETECTION AND PIPELINE
# ==============================================================================


@pytest.mark.parametrize(
    "name",
    [
        "url",
        "website",
        "_client_web_site",
        "Web_Site",
        "homepage",
        "profile_url",
        "Link",
    ],
)
def test_url_cleaner_claims_url_like_column_names(name: str) -> None:
    """Column names such as url, website, homepage and Link tell us what the column holds. The cleaner claims them at full score."""
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert UrlCleaner().match_score(df, (name,)) == 1.0


@pytest.mark.parametrize("name", ["link_id", "curly", "site", "name", "web"])
def test_url_cleaner_ignores_other_column_names(name: str) -> None:
    """Names like link_id, site and web only resemble URL words. They should score zero, so we do not clean columns that are not addresses."""
    df = PandasDataFrame(df=pd.DataFrame({name: ["x"]}))

    assert UrlCleaner().match_score(df, (name,)) == 0.0


def test_resolver_assigns_url_cleaner_to_each_url_column() -> None:
    """Given a frame with two URL-style columns and a name column, the resolver should hand the URL cleaner to the two URL ones and skip the other."""
    cols = {"website", "_client_web_site", "name"}
    df = PandasDataFrame(df=pd.DataFrame({col: ["v"] for col in cols}))

    assignments = Resolver(cleaners=(UrlCleaner(),)).resolve(df, cols)

    assert {a.role_columns["value"] for a in assignments} == {
        "website",
        "_client_web_site",
    }


def test_pipeline_cleans_url_column_in_place() -> None:
    """An end-to-end run on a small column. Good values are tidied in place, and junk, nulls and blanks all end up as null."""
    df = PandasDataFrame(
        df=pd.DataFrame({"website": ["WWW.Example.com/", "junk", None, "  "]})
    )

    cleaned = Pipeline(cleaners=(UrlCleaner(),)).fit_transform(df)

    assert cleaned.df is not None
    assert cleaned.df["website"].tolist() == [
        "https://www.example.com",
        None,
        None,
        None,
    ]


def test_url_cleaner_strips_html_first() -> None:
    """URLs can come wrapped in HTML. Simple tags are removed first, but content inside a style tag is not trusted and gives null."""
    from dataclean import UrlCleaner

    cleaner = UrlCleaner()
    assert cleaner.clean_row("<b>https://example.com</b>") == "https://example.com"
    assert cleaner.clean_row("<style>https://x.com</style>") is None


def test_url_cleaner_reads_link_targets_first() -> None:
    """In an anchor tag the href is the real address, so we use it ahead of the visible text. If the href is not a web link, such as mailto or a page anchor, we fall back to the text."""
    from dataclean import UrlCleaner

    cleaner = UrlCleaner()
    assert cleaner.clean_row('<a href="https://x.com/a">our site</a>') == (
        "https://x.com/a"
    )
    # Links that are not web addresses fall back to the text.
    assert cleaner.clean_row('<a href="mailto:a@b.com">www.x.com</a>') == (
        "https://www.x.com"
    )
    assert cleaner.clean_row('<a href="#top">https://y.com</a>') == "https://y.com"
