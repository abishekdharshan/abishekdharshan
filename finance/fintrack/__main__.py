"""python3 -m fintrack <command>

  init           create the data folder with templates
  build          read everything, write ledger.csv + report.html, print a summary
  review         list the biggest uncategorized merchants (to write rules for)
  sync-wallets   download wallet history from the Zerion API (needs ZERION_API_KEY)
  demo           build a report from generated sample data
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from . import ledger, report
from .importers import zerion

DEFAULT_DATA = Path.home() / "fintrack-data"

TEMPLATES = {
    "rules.csv": """# Your categorization rules. Checked before the built-in ones (fintrack/default_rules.csv).
# pattern   = regular expression, case-insensitive, searched in the raw description
# category  = e.g. Groceries, Dining & Drinks, Rent & Housing, Salary, Transfer, Ignore (full list in README)
# merchant  = optional clean display name
# direction = optional: in / out
# account   = optional regex on the account folder name, or type:credit / type:checking
# Wrap a pattern in "double quotes" if it contains a comma.
pattern,category,merchant,direction,account
# ACME CORP,Salary,ACME paycheck,in,
# Zelle payment to JOHN SMITH,Rent & Housing,Rent,out,
# Zelle.*(SARAH|MOM),Gifts & Donations,,out,
""",
    "overrides.csv": """# Fix single transactions. Copy the id from ledger.csv (or hover a description in the report).
id,category,merchant,note
""",
    "wallets.csv": """# On-chain wallets to pull via the Zerion API (python3 -m fintrack sync-wallets).
address,label
# 0x0000000000000000000000000000000000000000,Main
""",
    "w2.csv": """# One row per W-2 (per employer per year). Boxes: gross = box 1 + pre-tax deductions,
# or just use the year-end "gross pay" from your last pay stub. taxes_withheld = federal + state + local + social security + medicare.
year,employer,gross_pay,taxes_withheld,pretax_deductions
""",
    "balances.csv": """# Optional account balance snapshots (e.g. year-end statements) for the wealth chart.
date,account,balance
# 2024-12-31,Robinhood,25000
""",
    "manual.csv": """# Anything without an export: cash, a bonus paid by check, an old account. Amount: + in, - out.
date,account,description,amount,category
""",
}


def data_dir(arg) -> Path:
    return Path(arg or os.environ.get("FINTRACK_DATA") or DEFAULT_DATA).expanduser()


def cmd_init(args) -> None:
    d = data_dir(args.data)
    (d / "raw").mkdir(parents=True, exist_ok=True)
    for name, body in TEMPLATES.items():
        p = d / name
        if not p.exists():
            p.write_text(body)
    print(f"Data folder ready: {d}")
    print("Next: put each account's CSV exports in raw/<Account name>/, e.g.")
    print(f"  {d / 'raw' / 'BofA Checking'}/")
    print(f"  {d / 'raw' / 'Chase Sapphire'}/")
    print("then run: python3 -m fintrack build")


def build(d: Path, open_report: bool = False) -> Path:
    if not (d / "raw").exists():
        sys.exit(f"No data folder at {d}. Run `python3 -m fintrack init` first (or pass --data).")
    ds = ledger.load(d)
    ledger.write_ledger(ds, d / "ledger.csv")
    out = d / "report.html"
    report.write_html(report.report_data(ds, datetime.now().strftime("%Y-%m-%d %H:%M")), out)
    report.print_summary(ds)
    print(f"\nLedger: {d / 'ledger.csv'}\nReport: {out}")
    if open_report:
        webbrowser.open(out.resolve().as_uri())
    return out


def cmd_build(args) -> None:
    build(data_dir(args.data), args.open)


def cmd_review(args) -> None:
    ds = ledger.load(data_dir(args.data))
    rows = report.uncategorized(ds, args.n)
    if not rows:
        print("Everything has a category.")
    for merchant, count, total, sample in rows:
        print(f"{report._money(total):>10}  {count:4d}x  {merchant[:32]:32}  {sample[:90]}")


def cmd_sync_wallets(args) -> None:
    key = os.environ.get("ZERION_API_KEY")
    if not key:
        sys.exit("Set ZERION_API_KEY (get one at https://developers.zerion.io).")
    d = data_dir(args.data)
    if not zerion.load_wallets(d):
        sys.exit(f"No wallets listed in {d / 'wallets.csv'}.")
    print("Syncing wallets from Zerion:")
    zerion.sync(d, key)
    print("Done. Run `python3 -m fintrack build` to refresh the report.")


def cmd_demo(args) -> None:
    from .demo import generate
    d = Path(args.out).expanduser()
    generate(d)
    build(d, args.open)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="fintrack", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in [("init", cmd_init, "create the data folder"), ("build", cmd_build, "build ledger + report"),
                            ("review", cmd_review, "list uncategorized merchants"),
                            ("sync-wallets", cmd_sync_wallets, "download wallet data from Zerion")]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--data", help=f"data folder (default: $FINTRACK_DATA or {DEFAULT_DATA})")
        sp.set_defaults(fn=fn)
        if name == "build":
            sp.add_argument("--open", action="store_true", help="open the report in your browser")
        if name == "review":
            sp.add_argument("-n", type=int, default=40)
    sp = sub.add_parser("demo", help="build a report from generated sample data")
    sp.add_argument("--out", default="demo-data", help="where to write the sample data (default: ./demo-data)")
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(fn=cmd_demo)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
