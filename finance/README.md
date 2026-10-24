# fintrack

A private, local report of everything you've earned and spent, across every
bank, card, brokerage, exchange and wallet. You drop in the CSV exports your
banks already give you; it builds one categorized ledger and an HTML report:

- earned vs spent vs saved, per year and per month, with year-over-year change
- spending by category per year, plus top merchants and a searchable transaction list
- gross pay and taxes from W-2s, savings rate, and balances over time
- a data-health section showing coverage gaps and uncategorized spending

No accounts, no logins, no cloud. Python 3.9+ standard library only. The one
network call is the optional Zerion API for on-chain wallets.

```sh
cd finance
python3 -m fintrack demo --open      # see a report built from fake data
python3 -m fintrack init             # create ~/fintrack-data
# ...put exports in ~/fintrack-data/raw/<Account name>/...
python3 -m fintrack build --open     # build ~/fintrack-data/report.html
```

## Privacy

Your data lives in `~/fintrack-data` (or `$FINTRACK_DATA`), **outside this
repository**, so it can't be committed by accident. `report.html` and
`ledger.csv` contain your full history. Treat them like bank statements.

## The data folder

```
~/fintrack-data/
  raw/
    BofA Checking 1111/        <- one folder per account; the folder name is the account name
      2024-2026.csv            <- any number of exports; overlapping date ranges are de-duplicated
    Chase Sapphire 2222/
    Amex 33333/
    Robinhood/
    Coinbase/
  rules.csv        your categorization rules (checked before the built-in ones)
  overrides.csv    fix individual transactions by id
  wallets.csv      on-chain addresses for `sync-wallets`
  w2.csv           gross pay / taxes / pre-tax deductions per year
  balances.csv     optional balance snapshots (e.g. year-end statements)
  manual.csv       anything without an export
  ledger.csv       OUTPUT: every transaction, categorized
  report.html      OUTPUT
```

Put "card", "credit" or the card's name (Sapphire, Amex, Visa...) in a credit
card's folder name, and "savings" in a savings account's. Known export formats
set this themselves; for others the name is the hint.

## Getting the exports

Download as far back as each site allows. Most banks' CSV download covers
about the last 18–24 months; older history comes from PDF statements (see
"Older history" below).

| Institution | Where | Notes |
|---|---|---|
| Bank of America (checking, cards) | Account → **Download** above the transaction list → "Microsoft Excel" (a CSV) | Checking includes running balances, which feed the balances chart |
| Chase (checking, savings, cards) | Account → download icon → **Spreadsheet (CSV)** → date range | One export per account |
| American Express | Statements & Activity → **Download** → CSV | One export per card. Tick "include additional details" to get Amex's categories |
| Citi | Account → transactions → **Download / Export** → CSV | |
| US Bank | Transaction list → **Download** → CSV | |
| Wells Fargo (checking, cards) | Account activity → **Download** → Comma Delimited | Has no header row; detected automatically |
| Capital One / 360 | Account → **Download Transactions** → CSV | |
| Apple Card | Wallet app → Apple Card → Card Balance → a monthly statement → **Export Transactions** → CSV | One file per month |
| Coinbase One Card | Coinbase → Credit card → Transactions → See all → **Export** | Emailed link, valid for 24 hours |
| Robinhood brokerage | Account → Reports and statements → **Account activity report** → CSV | Takes a few hours to generate. Covers the whole account history |
| Coinbase | Profile → Statements / Reports → **Transaction history** → CSV, all time | |
| Schwab (brokerage, bank) | History → Transactions → **Export** | |
| SoFi, Revolut, Wealthfront, others | Each has a CSV export somewhere in activity/statements | Read by the generic importer |
| Venmo, PayPal | Skip for now | Bank-side Venmo/Zelle rows already count as "P2P Payments" |
| Payroll (Gusto, Justworks, ...) | Documents → **W-2s** | Copy each year into `w2.csv`. Bank data only shows take-home pay |
| Wallets | List addresses in `wallets.csv`, then `ZERION_API_KEY=... python3 -m fintrack sync-wallets` | Full history and portfolio value over time |

If a file is reported as unrecognized, or its signs come out inverted, see
Troubleshooting.

## How money is counted

| Kind | Counts as | Examples |
|---|---|---|
| income | earned | Salary, Interest & Dividends, Crypto Rewards, Bonus & Other Income |
| expense | spent (refunds reduce it) | Rent & Housing, Groceries, Dining & Drinks, Travel, Shopping, Subscriptions, Taxes, P2P Payments ... |
| transfer | neither | Credit Card Payment, Transfer, Investment Transfer, Crypto Transfer, Ignore |
| investment | neither | Investment Trade (buys, sells, swaps) |

Card purchases are counted when you make them; paying the card bill is a
transfer. Money sent to Robinhood/Coinbase/Schwab is a transfer (it's still
yours), so **saved = earned − spent** includes what you invested.

Each transaction's category is decided by, in order:

1. `overrides.csv`: one transaction, by the `id` column in `ledger.csv`
2. `rules.csv`: your rules
3. the importer, for sources with transaction codes (Robinhood, Coinbase, Schwab, wallets)
4. `fintrack/default_rules.csv`: built-in rules for common merchants and banks
5. the bank's own category column, when the export has one
6. transfer matching: the same amount leaving one of your accounts and arriving in another within 5 days
7. otherwise Uncategorized (money out) / Uncategorized Income (money in) / Refunds & Credits (a credit on a card)

### Rules

`rules.csv` columns: `pattern,category,merchant,direction,account`.

```csv
pattern,category,merchant,direction,account
ACME CORP,Salary,ACME paycheck,in,
Zelle payment to JOHN SMITH,Rent & Housing,Rent,out,
"BOWERY BALLROOM|BROOKLYN STEEL",Entertainment,,,
REIMBURSEMENT,Ignore,,,
```

`pattern` is a case-insensitive regular expression searched in the raw
description. Quote it if it contains a comma. `direction` is `in` or `out`.
`account` is a regex on the folder name, or `type:credit` / `type:checking`.
A category name that isn't in the table above is treated as spending.

After `build`, the terminal and the report's "Needs a category" table list the
biggest uncategorized merchants. Writing rules for the top ten usually covers
most of the money. `python3 -m fintrack review -n 60` prints a longer list.

## Keeping it up to date (about 10 minutes a month)

1. Download last month's CSV from each account into its folder. Overlap is fine.
2. `python3 -m fintrack sync-wallets` if you track wallets.
3. `python3 -m fintrack build --open`
4. Add rules for anything new under "Needs a category".

## Older history

CSV downloads rarely reach back more than about two years. For earlier years:

- **W-2s** (`w2.csv`) give gross pay and taxes for every year. This is the
  clearest picture of how your income has grown.
- **Year-end balances** (`balances.csv`, from each December statement) give
  net worth over time.
- **Brokerages, Coinbase and wallets** export their full history.
- Detailed spending before then needs the banks' **PDF statements**. A
  statement parser is planned. Until then, `manual.csv` takes rough yearly
  totals if you want them.

## Troubleshooting

- **"unrecognized CSV layout"**: the file needs a header row with a date, a
  description and either an amount or debit/credit columns. Open it and
  check. If the header is fine, add the format to `FORMATS` in
  `fintrack/importers/banks.py`.
- **Signs inverted** (purchases showing as money in): the generic importer
  guesses from the data. Fix it with `raw/<Account>/_account.ini`:
  ```ini
  [account]
  sign = flip        ; or as-is
  type = credit      ; checking | savings | credit | brokerage | crypto
  ```
- **Transfers counted as spending or income**: write a rule mapping that
  description to `Transfer`, or add the other account's export so transfer
  matching can pair the two sides.
- **Spending jumps or drops between years**: check "Accounts and coverage" in
  the report. A card missing for part of the period looks like a change in
  spending.

## Development

```sh
cd finance
python3 -m unittest discover -s tests
```

`fintrack demo` writes sample exports in each institution's real layout, so
it runs the same importers as real data.
