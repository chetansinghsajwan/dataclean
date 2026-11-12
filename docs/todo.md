# Todo

Work for later that is not part of the [release plan](release-plan.md).

- Add benchmarks: measure cleaner throughput and detection time per engine
  (pandas, ibis, Spark), so speed changes can be compared.
- Auto-detect low-cardinality columns in `EnumCleaner`: today it needs `cases=`
  and is explicit-only. Later it should detect a column with few distinct
  values (for example `status`) and build its cases from the data.
- Use titles and suffixes to fill missing values in `GenderCleaner`: when the
  gender is blank, infer it from a title in a name column (`Mr`, `Mrs`, `Ms`,
  `Miss`) or a suffix. This needs the name column as an extra input role.
- Normalise street abbreviations in `AddressCleaner` (`St`, `Rd`, `Ave`,
  `Apt`). It is ambiguous without the country (`St` is Street or Saint, `Dr` is
  Drive or Doctor), so it needs the cleaned country (now an input) to choose the expansion.
