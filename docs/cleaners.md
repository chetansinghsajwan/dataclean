# Built-in Cleaners

All 14 cleaners live under `dataclean.cleaners`. Their constructor
parameters, expected input/output roles, and `match_score` heuristics are
summarized here; see [Concepts](concepts.md) for how `match_score` and
auto-detection fit together generally.

| Cleaner | Purpose | `match_score` heuristic | Auto-registered? |
|---|---|---|---|
| `AddressCleaner` | Splits/normalizes a multi-column address | none (always `0.0` — multi-column) | Yes |
| `BoolCleaner` | Normalizes truthy/falsy values | name prefix/suffix + value sampling | Yes |
| `CountryCleaner` | Normalizes country names/codes | `"country"` in column name | Yes |
| `DateTimeCleaner` | Parses/reformats dates, times, datetimes | `date`/`time`/`timestamp`/`_at` in column name | Yes |
| `EmailCleaner` | Extracts/normalizes an email address | `"email"` in column name | Yes |
| `EnumCleaner` | Generic categorical value normalizer | name prefix/suffix/word + value sampling | **No** — needs `cases=` |
| `FilePathCleaner` | Normalizes file names and paths | `file`/`path`/`dir`/`folder` word in column name | Yes |
| `GenderCleaner` | Normalizes gender values | `gender`/`sex` in column name + value sampling | Yes |
| `NameCleaner` | Recognizes personal-name columns (values unchanged, placeholders nulled) | person-name column tokens (`fname`/`lname`/`first_name`/`surname`/...) | Yes |
| `NumericCleaner` | Parses/reformats numeric values | name tokens (30%) + value sampling (70%) | Yes |
| `PhoneCleaner` | Parses/reformats phone numbers | `phone`/`tel`/`mobile`/`fax`/`contact_no` in column name | Yes |
| `TextCleaner` | General free-text normalization | text-ish tokens, else a `0.1` baseline (never `0.0`) | Yes |
| `UrlCleaner` | Normalizes web addresses | `url`/`uri`/`href`/`link` word or `website`/`homepage` in column name | Yes |
| `UuidCleaner` | Normalizes UUID strings | `uuid`/`guid`/`pk_id`/`session_token` in column name | Yes |

## AddressCleaner

Multi-column cleaner: takes address parts in and produces normalized address
components out. No configuration options beyond the base `tags`/`inplace`.

- **Inputs**: `address_line1`, `address_line2`, `address_line3`, `town`,
  `county` and `postcode`, all optional. A group forms from any one matching
  column, and a row is cleaned even when its first line is empty.
- **Outputs**: `state`, `postcode`, `address_line`, `street`, `house_no`,
  `town`, `address_line2`, `address_line3`.
- **Behavior**: removes HTML tags (and `script`/`style` content) from every
  part; nulls a placeholder (`null`, `none`, `undefined`, `n/a`, `-`) in a
  line, town or county; collapses whitespace in each address line; title-cases `town`
  and `county` when they are written all lower or all upper case and look like
  a place name (mixed case such as "McDonald Heights" is kept); uppercases the
  postcode, drops hyphens, collapses whitespace and nulls a value with no
  letter or digit (such as `???`); a UK postcode gets one space before its last
  three characters, and others keep their spacing;
  splits `address_line1` on whitespace, where a leading numeric token becomes
  `house_no` and the remainder becomes `street`.
- **Country**: there is no country input or output. `CountryCleaner` owns every
  country column, including the country of an address, and cleans it in place.

!!! note "Known gaps"
    The `state` output column is populated from the cleaned **county** value,
    not a separate "state" concept: treat `state` as "cleaned county". Because
    no input is required, a lone column whose name contains a hint such as
    `city` or `county` is claimed as an address group.

An output is written only when its input role has a column: a lone `town`
column is cleaned in place and adds no other columns. With several roles, the
output columns are named after the first column found.

::: dataclean.cleaners.AddressCleaner

## BoolCleaner

Subclass of `EnumCleaner`; normalizes truthy/falsy strings to a chosen
output shape.

- **Params**: `truthy_values`/`falsy_values` (defaults:
  `("true","1","yes","t","y","active")` /
  `("false","0","no","f","n","inactive")`), `extra_truthy_values`/
  `extra_falsy_values` (appended), `out_format` (`Format.TRUEFALSE` (native
  `True`/`False`, default), `TRUEFALSE_STR`, `TF`, `BINARY` (`"1"`/`"0"`),
  `YESNO` (`"Yes"`/`"No"`)), `out_case` (`TextCase`, applied to string
  outputs only), `match_prefixes`/`match_suffixes` (defaults:
  `("is","has","active","status","flag")` / `("active","status","flag")`)
  plus their `extra_*` counterparts.
- **Output**: single column; `DataType.BOOL` when `out_format ==
  TRUEFALSE`, otherwise `DataType.STR`.
- **Behavior**: exact, case-insensitive match against the truthy/falsy
  variant lists; unrecognized input returns `None`.
- **Auto-detection**: columns already typed boolean always match. For
  **numeric** columns the column name is ignored and *every* sampled value
  must be a recognized flag (e.g. only `0` and `1`); see
  [EnumCleaner](#enumcleaner). Other columns match by name, or by the
  fraction of values that are recognized.

!!! note "`Format.YN` is not implemented"
    `BoolCleaner.Format` declares a `YN` member, but it isn't handled by the
    cleaner's internal case builder — constructing `BoolCleaner(out_format=BoolCleaner.Format.YN)`
    raises `ValueError`. Use `YESNO` instead.

```python
from dataclean import BoolCleaner

BoolCleaner(out_format=BoolCleaner.Format.TRUEFALSE).clean_row("yes")  # -> True
BoolCleaner(out_format=BoolCleaner.Format.YESNO).clean_row("T")  # -> "Yes"
BoolCleaner(out_format=BoolCleaner.Format.BINARY).clean_row("active")  # -> "1"
```

::: dataclean.cleaners.BoolCleaner

## CountryCleaner

- **Params**: `in_format` (a `Format` or tuple of them — `ALPHA2`, `ALPHA3`,
  `NAME`, `NAME_FUZZY`, or `AUTO` (default) which tries all four in that
  order), `out_format` (`NAME` (default), `ALPHA2`, or `ALPHA3` only —
  `AUTO`/`NAME_FUZZY` aren't valid renderers and raise `ValueError`),
  `fuzzy_match_thresold` (`float`, default `0.9` — minimum
  `rapidfuzz.fuzz.WRatio` similarity for fuzzy name lookups).
- **Output**: single column, role `country`.
- **Behavior**: lowercases the input, then tries exact alpha-2, exact
  alpha-3, `pycountry`'s built-in fuzzy search, and finally custom
  `rapidfuzz`-based fuzzy matching against every country name, in that
  order; first hit wins.

!!! note "Parameter spelling"
    The threshold constructor parameter is spelled `fuzzy_match_thresold`
    (missing the "h") — that is the real, public parameter name.

```python
from dataclean import CountryCleaner

CountryCleaner().clean_row("IN")  # -> "India"
CountryCleaner(
    in_format=CountryCleaner.Format.ALPHA2, out_format=CountryCleaner.Format.ALPHA3
).clean_row("IN")  # -> "IND"
CountryCleaner(in_format=CountryCleaner.Format.NAME_FUZZY).clean_row(
    "hi indIA"
)  # -> "India"
```

::: dataclean.cleaners.CountryCleaner

## DateTimeCleaner

- **Params**: `out_format` (`Format.AUTO` (default), `ISO_DATETIME` (e.g.
  `2026-06-19T22:45:00`), `ISO_DATE`, `ISO_TIME`, `INDIAN_DATE` (e.g.
  `19-06-2026`)). With `AUTO` the pipeline reads the whole column and writes
  one layout: `ISO_DATE` if every value is a date (a datetime at midnight
  counts as a date), `ISO_TIME` if every value is a time, otherwise
  `ISO_DATETIME`. When a column mixes only dates and times, its name decides:
  a `time` name without `date` means time, anything else means date. A column
  never mixes layouts.
- **Output**: single STR column.
- **Auto-detection**: matches by column name, but never a column that already
  has a date, datetime or time type — there is nothing to parse, and cleaning
  it would turn the typed values into strings.
- **Behavior**: tries a fixed, non-configurable list of input formats in
  order (`"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%dT%H:%M:%S"`, `"%Y-%m-%d"`,
  `"%d-%m-%Y"`, `"%d/%m/%Y"`, `"%H:%M:%S"`, `"%I:%M %p"`) until one parses,
  then renders per `out_format`. Requesting a date-shaped output from a
  time-only parse (or vice versa) returns `None`.

```python
from dataclean import DateTimeCleaner

DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_DATE).clean_row(
    "19-06-2026"
)  # -> "2026-06-19"
DateTimeCleaner(out_format=DateTimeCleaner.Format.ISO_TIME).clean_row(
    "10:45 PM"
)  # -> "22:45:00"
```

::: dataclean.cleaners.DateTimeCleaner

## EmailCleaner

- **Params**: `keep_tags` (default `True`, keep `+tag` in the local part), `keep_dots` (default
  `True`), `lowercase` (default `True`), `output_format` (`FULL` (default, single combined string)
  or `COMPONENTS` (separate `local`/`tag`/`domain` columns)), `fix_domain_typos` (default `True`,
  correct a domain one edit (short domains) or two edits (9+ characters) from a known provider).
- **Output**: `FULL` → one column; `COMPONENTS` → `local`, `tag`, `domain`.
- **Behavior**: removes HTML tags (reading `mailto:` links first), then finds the first email-shaped
  substring in the value (regex search, not full-string match — extra text around the address is
  fine but a *second* email in the same value is ignored), splits it into local/tag/domain, applies
  the configured options, and reassembles.
- **Domain typos**: `gmial.com` and `gmail.con` become `gmail.com`. Only
  domains from `KNOWN_EMAIL_DOMAINS` are targets, a known domain is never
  changed, and a domain equally close to two providers is left as is.

```python
from dataclean import EmailCleaner

EmailCleaner().clean_row(" User.Name+Tag@Gmail.com ")  # -> "user.name+tag@gmail.com"
EmailCleaner().clean_row("john@gmial.com")  # -> "john@gmail.com"
```

::: dataclean.cleaners.EmailCleaner

## EnumCleaner

The generic categorical-value normalizer that `BoolCleaner` and
`GenderCleaner` are built on. Unlike the others, it has **no sensible
default** and is not auto-registered — you must construct it with `cases=`.

- **Params**: `cases` (**required**) — either a plain iterable of exact
  values, or a mapping of canonical output value → match spec, where a spec
  is a string (exact match), an iterable of strings (exact match against
  any), or a matcher object (see below); `cleaner_matching_prefixes`/
  `cleaner_matching_suffixes`/`cleaner_matching_words` — column-name
  heuristics for the `match_score` fast path.
- **Matcher classes**, nested on `EnumCleaner` and usable directly in a
  `cases` mapping: `EnumCleaner.ExactMatcher(variants, case_sensitive=True)`,
  `EnumCleaner.RegexMatcher(pattern, case_sensitive=True)`,
  `EnumCleaner.FuzzyMatcher(variants, threshold=0.9, case_sensitive=True)`,
  `EnumCleaner.CombinedMatcher(matchers)` (OR of sub-matchers).
- **Behavior**: cases are tried in the order given; the first matcher that
  accepts the value wins and its canonical key is returned, else `None`.
- **`match_score`**: if a configured prefix/suffix/word matches the column
  name, returns `MAX_SCORE` immediately without touching the data. Otherwise
  it samples the 100 most frequent distinct non-null values from the column
  and returns the frequency-weighted fraction accepted by any case — this
  same pattern is inherited by `BoolCleaner` and `GenderCleaner`. The
  exception is **numeric** columns (IDs and codes): the name is ignored and
  every sampled value must be accepted by a case, otherwise the score is `0`,
  so a mostly-`1` ID column is never mistaken for an enum or flag.

```python
from dataclean import EnumCleaner

EnumCleaner(cases={"active": ["active", "1"], "inactive": ["inactive", "0"]}).clean_row(
    "1"
)
# -> "active"
```

::: dataclean.cleaners.EnumCleaner

## FilePathCleaner

- **Params**: `separator` (`"/"` (default) or `"\\"`), `lowercase_extension`
  (default `True`).
- **Output**: single STR column, cleaned in place.
- **Behavior**: trims whitespace, invisible characters and wrapping quotes,
  turns backslashes into `separator`, collapses repeated separators (a leading
  pair, as in a network share, is kept), drops `.` segments inside the path
  and lowercases the file extension. The name keeps its case and `..` segments
  are kept. Values with control characters, `< > " | ? *`, a colon outside a
  drive prefix, or only dots and separators become `None`.
- **Detection**: names with a `file`, `path`, `dir` or `folder` word, or
  `filename`/`filepath`/`directory`. Names with a `url`, `uri`, `link`,
  `href` or `id` word (`url_path`, `file_id`) are left alone.

```python
from dataclean import FilePathCleaner

FilePathCleaner().clean_row(
    '"C:\\Users\\Ann\\Report.DOCX"'
)  # -> "C:/Users/Ann/Report.docx"
```

::: dataclean.cleaners.FilePathCleaner

## GenderCleaner

Subclass of `EnumCleaner`.

- **Params**: `format` (`Format.FULL` (default, `"Male"`/`"Female"`/`"Other"`),
  `CHAR` (`"M"`/`"F"`/`"O"`), `BINARY` (`"1"`/`"0"`/`"-1"`)), `case`
  (`TextCase`, applied to `FULL`/`CHAR` labels only), `genders` (mapping of
  canonical key → variant list; default covers `male`/`female`/`other`),
  `extra_genders` (merged on top, overriding same-key entries),
  `cleaner_matching_words` (default `["gender", "sex"]`), `fuzzy_threshold`
  (default `0.9`).

!!! note "Two parameters are currently no-ops"
    `cleaner_matching_words` passed to the constructor is **not** actually
    used — `GenderCleaner` always passes its own class default
    (`["gender", "sex"]`) to the underlying `EnumCleaner` regardless of what
    you pass here. `fuzzy_threshold` is accepted but fuzzy matching is dead
    code in the current implementation — only exact, case-insensitive
    matching is active. Don't rely on either until this is fixed upstream.

```python
from dataclean import GenderCleaner

GenderCleaner(format=GenderCleaner.Format.CHAR).clean_row("woman")  # -> "F"
GenderCleaner().clean_row("boy")  # -> "Male"
```

::: dataclean.cleaners.GenderCleaner

## NameCleaner

Recognizes personal-name columns; it does **not** change their values, except
that placeholders become null.

- **Params**: `null_tokens` (default `null`, `none`, `undefined`, `n/a`, `-`;
  compared case-insensitively). `na` and `nan` are not in it, since they are
  real names.
- **Output**: single column, same name as the input.
- **Behavior**: `clean_row` removes HTML tags (and `script`/`style` content),
  removes invisible characters (zero-width spaces, BOMs) and turns control
  characters such as tabs into spaces, then returns the value, or None for a
  placeholder or nothing left. It exists so that
  auto-detection claims name columns (and no other cleaner does). Like every
  cleaner, values still get the pipeline's input normalization: surrounding
  whitespace is stripped and blank strings become null. Casing is
  deliberately left alone, because name fields often hold acronyms, initials
  and company names that title-casing would damage.
- **`match_score`**: name-based only, and only for string columns. Matches
  `fname`/`lname`/`mname` (standalone or concatenated, e.g. `lnamefname`) and
  `first_name`, `last_name`, `middle_name`, `full_name`, `given_name`,
  `family_name`, `maiden_name`, `forename`, `surname`. A bare `name` column
  is deliberately not matched (it is often a company or product name), nor
  are `username`, `filename` or `colname`.

```python
from dataclean import NameCleaner

NameCleaner().clean_row("McDonald")  # -> "McDonald"
NameCleaner().clean_row("HBOS")  # -> "HBOS"
```

::: dataclean.cleaners.NameCleaner

## NumericCleaner

- **Params**: `out_format` (`Format.FLOAT` (default) or `INT`), `precision`
  (decimal places, half-up rounding; default `3`; `None` skips rounding),
  `parse_suffixes` (default `False` — interpret trailing k/m/b/t as
  ×1e3/1e6/1e9/1e12).
- **Output**: single column, `DataType.LONG` or `DataType.DOUBLE` per
  `out_format`. Note `clean_row` itself returns a numeric *string* — the
  declared output `dtype` is what the engine casts it with downstream.
- **Behavior**: strips currency symbols/thousands separators, collapses
  accidental double decimal points (`"150..50"` → `"150.5"`), rejects
  non-finite results, and applies `Decimal`-based half-up rounding.
- **`match_score`**: 30% weight from column-name tokens (`amount`, `price`,
  `count`, `quantity`, `revenue`, `total`) + 70% weight from actually running
  `clean_row` against up to 100 sampled raw values and measuring the success
  rate — a different sampling mechanism than `EnumCleaner`'s.

```python
from dataclean import NumericCleaner

NumericCleaner(out_format=NumericCleaner.Format.FLOAT, precision=2).clean_row(
    "14.555"
)  # -> "14.56"
NumericCleaner(parse_suffixes=True).clean_row("1.5M")  # -> "1500000.0"
NumericCleaner().clean_row("₹ 1,500.50")  # -> "1500.5"
```

::: dataclean.cleaners.NumericCleaner

## PhoneCleaner

- **Params**: `out_format` (`Format.E164` (default, e.g. `+14155552671`),
  `INTERNATIONAL`, `NATIONAL`, `RAW_DIGITS`), `default_regions` (tuple of
  region codes to try, in order, when the number has no leading `+`;
  default `()`).
- **Output**: single column, role `phone`.
- **Behavior**: removes HTML tags, then delegates to the `phonenumbers` library. Before parsing it
  converts scientific-notation-looking strings to plain digits, turns digits
  of other scripts (such as Arabic-Indic) into `0-9`, strips a leading label
  (`tel:`, `mobile:`) and a trailing note (`(Mobile)`, `(fax)`), and reads a
  leading `00` as `+`. It then tries each region (the row's `country` first,
  then `default_regions`; or none, if the value is self-contained e.g.
  `+91...`) until one parses as a valid number. Extensions are dropped.
- **Several numbers in one cell** (split by `/`, `;`, `|`, `,`, `&` or `or`)
  give the first one that cleans; `None` if none does.
- **Country column**: when a table has several country columns, the phone
  columns take the one named exactly `country`, not a specific one such as
  `_client_country_of_incorporation`.

!!! warning "Numbers that cannot be judged are kept, not dropped"
    If no region is known (no `country` input and `default_regions` is
    empty) and the number has no leading `+`, it can't be validated, so a
    value with 1 to 15 digits is returned unchanged (stripped) instead of
    `None`. A value with no digit, such as `abc` or `n/a`, or with more than 15
    (the E.164 maximum) is `None`. A vanity number such as `1-800-FLOWERS` is
    always `None`. With a
    known region, a number that isn't valid there also returns `None`. Set
    `default_regions` (or provide a country column) to get consistent
    formatting.

```python
from dataclean import PhoneCleaner

PhoneCleaner(default_regions=("IN",)).clean_row("9876543210")  # -> "+919876543210"
PhoneCleaner().clean_row("+91 98765 43210")  # -> "+919876543210"
```

::: dataclean.cleaners.PhoneCleaner

## TextCleaner

- **Params**: `lowercase` (default `True`), `remove_html` (default `True`),
  `remove_urls` (default `True`), `remove_emails` (default `True`),
  `remove_punctuation` (default `False`), `remove_digits` (default `False`),
  `replace_newlines_with_spaces` (default `True`).
- **Output**: single STR column.
- **Behavior**: builds a fixed regex pipeline once at construction (order:
  HTML → URLs → emails → digits → punctuation → newlines → whitespace
  collapse → lowercase), applies it to the value, and returns `None` if the
  result is empty.
- **`match_score`**: `0.8` for text-ish column names (`text`, `description`,
  `comment`, `notes`, `summary`, `review`), but falls back to a **`0.1`
  baseline** rather than `0.0` for everything else — `TextCleaner` is meant
  as a generic free-text catch-all, so it never scores a flat zero.

```python
from dataclean import TextCleaner

TextCleaner(remove_html=True, remove_urls=True, remove_emails=True).clean_row(
    "<p>Contact admin@test.com or visit https://site.com.</p>"
)
# -> "contact or visit"
```

::: dataclean.cleaners.TextCleaner

## UrlCleaner

- **Params**: `out_format` (`Format.FULL` (default) or `DOMAIN`, the host
  only), `default_scheme` (`"https"` (default) or `"http"`).
- **Output**: single STR column, cleaned in place.
- **Behavior**: removes HTML tags (reading link `href` values first, except `mailto:`, `tel:` and
  `#` ones), then trims whitespace, invisible characters and wrapping quotes or `<>`, adds
  `default_scheme` when missing (`www.x.com`, `//x.com`), lowercases the scheme and host, and drops
  the default port, a trailing dot on the host and a lone `/` after it. Path, query, fragment,
  `www.` and the `http` scheme are kept. Only `http` and `https` are accepted; other schemes
  (`javascript:`, `mailto:`, `ftp:`), invalid hosts and values with spaces become `None`. Of several
  URLs in one value (separated by `;`, `|`, `,` or `or`) the first valid one is used.
  Internationalized hosts stay in Unicode.
- **Detection**: names with a `url`, `uri`, `href` or `link` word, or
  `website`/`homepage`. A name with an `id` word is left alone.

```python
from dataclean import UrlCleaner

UrlCleaner().clean_row("WWW.Example.com:443/")  # -> "https://www.example.com"
```

::: dataclean.cleaners.UrlCleaner

## UuidCleaner

- **Params**: `out_format` (`Format.STANDARD` (default, hyphenated),
  `COMPACT` (32 raw hex chars), `URN` (`urn:uuid:...`)), `allowed_versions`
  (`set[int] | None`, e.g. `{4, 7}`; `None` accepts any valid version).
- **Output**: single STR column.
- **Behavior**: strips surrounding quote/bracket characters and a leading
  `urn:uuid:` prefix, lowercases, and parses as a UUID; falls back to
  extracting exactly 32 hex characters from stray-delimited text if direct
  parsing fails. Filters by `allowed_versions` if set.

```python
from dataclean import UuidCleaner

UuidCleaner().clean_row("{123E4567-E89B-12D3-A456-426614174000}")
# -> "123e4567-e89b-12d3-a456-426614174000"
UuidCleaner(allowed_versions={7}).clean_row(some_v4_uuid)  # -> None (wrong version)
```

::: dataclean.cleaners.UuidCleaner

## Columns left uncleaned

Some columns have no cleaner on purpose. Identifier-like columns such as
`username` and `colname` are not claimed by any cleaner, so their values pass
through unchanged. To clean one anyway, name a cleaner for it with
`column_cleaners` (see [Configuration](configuration.md)), for example
`column_cleaners={"colname": TextCleaner()}`.

## What's next

See [Writing a Custom Cleaner](custom-cleaners.md) if none of these fit your
data.
