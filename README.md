# Filing Radar

Statutory risk across a UK accountancy practice's whole client book, built
entirely from the **public Companies House register**. No API key, no paid
data, no access to anyone's practice software.

Live site: https://bomj987.github.io/filing-radar/
Example report: https://bomj987.github.io/filing-radar/r/demo/

## What it finds

For every active company registered at a firm's address:

- **Directors who must verify their identity and have not.** Under ECCTA the
  deadline for existing directors is **18 November 2026**, and Companies House
  publishes a *personal* due date per officer that is often earlier.
- **Accounts overdue or due within 30 days**, priced at the Companies House
  late-filing scale (£150 / £375 / £750 / £1,500 by lateness).
- **Confirmation statements overdue or due.**
- **Active companies with no serving officers.**

Company secretaries are deliberately excluded: ECCTA does not require them to
verify. Companies House distinguishes the two — an officer who must verify has
an `Identity verification due` or `Identity verification status` field on the
register; a secretary has neither. Getting this wrong produced a 50% false
positive rate in the first version and is covered by a regression test.

## Running it

Python 3.11+. No dependencies — standard library only.

```bash
cd engine
python3 -m filingradar.cli \
  --address "43a St Mary's Road Market Harborough LE16 7DS" \
  --firm    "HARMAN & HUNTER ACCOUNTANTS AND BUSINESS ADVISERS LTD" \
  --out     ../r/demo \
  --today   2026-08-30
```

Writes `index.html`, `report.json` and `report.csv` into `--out`.
`--today` fixes the reference date so runs are reproducible.

### Options

| Flag | Meaning |
|---|---|
| `--address` | registered office address of the practice |
| `--firm` | practice name, used in the report heading |
| `--out` | output directory |
| `--exclude` | comma-separated company numbers to drop (usually the practice itself) |
| `--limit` | cap the number of companies, for a quick look |
| `--cache` | on-disk HTTP cache directory (default `.cache`) |
| `--today` | `YYYY-MM-DD`, overrides the current date |

## Tests

```bash
cd engine && python3 -m unittest discover -s tests -t . -v
```

43 tests, no network. Parser tests are pinned to real Companies House pages
saved in `fixtures/`, so if the registry's markup changes the suite fails
loudly instead of silently producing wrong reports.

## Being a good citizen of a government service

`fetch.py` caches every page on disk, spaces requests (0.6s default), retries
with backoff, and identifies itself in the User-Agent. The register is a public
service paid for by other people; do not hammer it.

## Data licence

Companies House data is published under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## Status

Pre-revenue. Nobody has paid for this. The demand hypothesis is being tested
and the thresholds for killing it were fixed in advance.
