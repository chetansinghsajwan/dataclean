# Built-in Cleaners

All 11 cleaners live under `dataclean.cleaners`. Their constructor
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
| `GenderCleaner` | Normalizes gender values | `gender`/`sex` in column name + value sampling | Yes |
| `NumericCleaner` | Parses/reformats numeric values | name tokens (30%) + value sampling (70%) | Yes |
| `PhoneCleaner` | Parses/reformats phone numbers | `phone`/`tel`/`mobile`/`fax`/`contact_no` in column name | Yes |
| `TextCleaner` | General free-text normalization | text-ish tokens, else a `0.1` baseline (never `0.0`) | Yes |
| `UuidCleaner` | Normalizes UUID strings | `uuid`/`guid`/`pk_id`/`session_token` in column name | Yes |

## AddressCleaner

Multi-column cleaner: takes address parts in and produces normalized address
components out. No configuration options beyond the base `tags`/`inplace`.

- **Inputs**: `county` (optional), `country` (optional), `address_line1`
  (**required**), `address_line2` (optional — see note below),
  `address_line3` (optional).
- **Outputs**: `country`, `state`, `postcode`, `address_line`, `street`,
  `house_no`.
- **Behavior**: strips/title-cases `country` and `county`; strips
  `address_line3`, uppercases it, and removes hyphens to derive `postcode`;
  splits `address_line1` on whitespace — a leading numeric token becomes
  `house_no`, the remainder becomes `street`.

!!! note "Known gaps"
    `address_line2` (city) is accepted as an input but is **not currently
    used** by `clean_row` — it has no effect on the output. The `state`
    output column is populated from the cleaned **county** value, not a
    separate "state" concept — treat `state` as "cleaned county" until this
    is revisited.

```python
from dataclean import AddressCleaner

AddressCleaner().clean_row(
    county="uttar pradesh",
    country="in",
    address_line1="221 Baker Street",
    address_line3="ncr-110001",
)
# -> ("In", "Uttar Pradesh", "NCR110001", "221 Baker Street", "Baker Street", "221")
```

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

- **Params**: `out_format` (`Format.ISO_DATETIME` (default, e.g.
  `2026-06-19T22:45:00`), `ISO_DATE`, `ISO_TIME`, `INDIAN_DATE` (e.g.
  `19-06-2026`)).
- **Output**: single STR column.
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

- **Params**: `keep_tags` (default `True`, keep `+tag` in the local part),
  `keep_dots` (default `True`), `lowercase` (default `True`),
  `output_format` (`FULL` (default, single combined string) or `COMPONENTS`
  (separate `local`/`tag`/`domain` columns)).
- **Output**: `FULL` → one column; `COMPONENTS` → `local`, `tag`, `domain`.
- **Behavior**: finds the first email-shaped substring in the value (regex
  search, not full-string match — extra text around the address is fine but
  a *second* email in the same value is ignored), splits it into
  local/tag/domain, applies the configured options, and reassembles.

```python
from dataclean import EmailCleaner

EmailCleaner().clean_row(" User.Name+Tag@Gmail.com ")  # -> "user.name+tag@gmail.com"
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
  same pattern is inherited unchanged by `BoolCleaner` and `GenderCleaner`.

```python
from dataclean import EnumCleaner

EnumCleaner(cases={"active": ["active", "1"], "inactive": ["inactive", "0"]}).clean_row(
    "1"
)
# -> "active"
```

::: dataclean.cleaners.EnumCleaner

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

## NumericCleaner

- **Params**: `out_format` (`Format.FLOAT` (default) or `INT`), `precision`
  (decimal places, half-up rounding; default `3`; `None` skips rounding),
  `parse_suffixes` (default `False` — interpret trailing k/m/b/t as
  ×1e3/1e6/1e9/1e12).
- **Output**: single column, `DataType.INT` or `DataType.FLOAT` per
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
- **Behavior**: delegates to the `phonenumbers` library. Converts
  scientific-notation-looking strings to plain digits first, then tries
  each region in `default_regions` (or none, if the value is
  self-contained e.g. `+91...`) until one parses as a valid number.

!!! note "`country` parameter is currently unused"
    `clean_row(self, v, country=None)` accepts a second `country` argument
    for signature/schema compatibility, but it currently has no effect on
    cleaning — region selection is driven only by `default_regions`.

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

## What's next

See [Writing a Custom Cleaner](custom-cleaners.md) if none of these fit your
data.
