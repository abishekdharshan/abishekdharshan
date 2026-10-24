# fintrack: notes for Claude

Personal-finance ledger + HTML report. Stdlib-only Python 3.9+. See README.md.

## Never commit personal data

This repository is public. The user's data lives in `~/fintrack-data` (or
`$FINTRACK_DATA`), outside the repo. Never copy exports, `ledger.csv`,
`report.html`, account numbers, employer names or wallet addresses into the
repo. Personal rules go in the data folder's `rules.csv`, never in
`fintrack/default_rules.csv`. Default rules hold generic merchant and bank
patterns only.

## Routine maintenance ("update my finances")

1. `python3 -m fintrack build` (add `--data DIR` if not the default).
2. Read the summary: coverage per account, then "Needs a category".
3. For the biggest uncategorized merchants, add rules to `<data>/rules.csv`.
   Look at the raw descriptions in `<data>/ledger.csv` before writing a
   pattern, and keep patterns specific.
4. Rebuild and check that the yearly totals moved the way you expect.
5. Check "Excluded from earned / spent". Credit Card Payment and Investment
   Transfer should be near zero net when both sides are present. A large
   imbalance means a missing account, or a transfer being counted as
   income or spending.

## Code map

- `fintrack/importers/`: format detection (`__init__.py`), bank and card CSVs
  (`banks.py`), Robinhood / Coinbase / Schwab (`brokers.py`), wallets via
  the Zerion API (`zerion.py`)
- `fintrack/categorize.py`: rule precedence, transfer matching, merchant names
- `fintrack/ledger.py`: loads the data folder into a `Dataset`
- `fintrack/report.py` + `report_template.html`: aggregation and the report.
  All charts are vanilla JS/SVG in the template
- `fintrack/demo.py`: fake data in each institution's real export layout

Run `python3 -m unittest discover -s tests` after changes. For report changes,
render `python3 -m fintrack demo` and look at it in light and dark mode.
