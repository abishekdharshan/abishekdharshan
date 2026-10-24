"""Load everything in the data folder into one categorized ledger."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from . import categorize as cat
from .importers import import_file, read_account_options, zerion
from .importers.common import parse_date, parse_money
from .model import Balance, Txn, assign_ids

SKIP_DIRS = {"cache"}


@dataclass
class AccountInfo:
    name: str
    type: str = ""
    formats: set = field(default_factory=set)
    files: int = 0
    count: int = 0
    first: str = ""
    last: str = ""


@dataclass
class Dataset:
    txns: list[Txn]
    balances: list[Balance]
    w2: list[dict]
    accounts: dict[str, AccountInfo]
    warnings: list[str]


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [line for line in f if line.strip() and not line.lstrip().startswith("#")]
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(lines)]


def load(data_dir: Path) -> Dataset:
    warnings: list[str] = []
    by_id: dict[str, Txn] = {}
    balances: list[Balance] = []
    accounts: dict[str, AccountInfo] = {}

    def add(group: list[Txn]) -> None:
        assign_ids(group)
        for t in group:
            by_id.setdefault(t.id, t)

    raw = data_dir / "raw"
    for path in sorted(raw.glob("*")) if raw.exists() else []:
        if path.is_file() and path.suffix.lower() == ".csv":
            warnings.append(f"raw/{path.name}: put each account's files in its own folder, "
                            f"e.g. raw/Chase Sapphire/{path.name} (skipped)")
    for folder in sorted(p for p in raw.iterdir() if p.is_dir()) if raw.exists() else []:
        if folder.name in SKIP_DIRS or folder.name.startswith("."):
            continue
        account = folder.name
        opts = read_account_options(folder)
        info = accounts.setdefault(account, AccountInfo(account))
        files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.name.startswith(("_", ".")))
        for path in files:
            rel = path.relative_to(data_dir)
            if path.suffix.lower() != ".csv":
                warnings.append(f"{rel}: only .csv exports are read (skipped)")
                continue
            try:
                fmt, txns, bals = import_file(path, account, opts)
            except Exception as e:  # one bad file shouldn't stop the report
                warnings.append(f"{rel}: could not read ({e})")
                continue
            if fmt is None:
                warnings.append(f"{rel}: unrecognized CSV layout (skipped) - see README 'Troubleshooting'")
                continue
            if not txns:
                warnings.append(f"{rel}: recognized as {fmt} but contained no transactions")
            info.formats.add(fmt)
            info.files += 1
            if txns:
                info.type = txns[0].account_type
            add(txns)
            balances.extend(bals)

    # Manual entries: cash, one-offs, anything without an export.
    manual = []
    for row in _rows(data_dir / "manual.csv"):
        date, amount = parse_date(row.get("date")), parse_money(row.get("amount"))
        if not date or amount is None:
            continue
        manual.append(Txn(date=date, account=row.get("account") or "Manual", description=row.get("description", ""),
                          amount=amount, source="manual", account_type="manual", category=row.get("category", "")))
    add(manual)

    groups, wallet_balances, wallet_warnings = zerion.load_cached(data_dir)
    for group in groups:
        add(group)
    balances.extend(wallet_balances)
    warnings.extend(wallet_warnings)

    for row in _rows(data_dir / "balances.csv"):
        date, bal = parse_date(row.get("date")), parse_money(row.get("balance"))
        if date and bal is not None and row.get("account"):
            balances.append(Balance(date, row["account"], bal))

    w2 = []
    for row in _rows(data_dir / "w2.csv"):
        try:
            year = int(row.get("year", ""))
        except ValueError:
            continue
        w2.append({
            "year": year, "employer": row.get("employer", ""),
            "gross": parse_money(row.get("gross_pay")) or 0.0,
            "taxes": parse_money(row.get("taxes_withheld")) or 0.0,
            "pretax": parse_money(row.get("pretax_deductions")) or 0.0,
        })

    user_rules, problems = cat.load_rules(data_dir / "rules.csv")
    default_rules, _ = cat.load_rules(cat.DEFAULT_RULES)
    warnings.extend(problems)
    txns = sorted(by_id.values(), key=lambda t: (t.date, t.account, t.amount))
    cat.categorize(txns, user_rules, default_rules, cat.load_overrides(data_dir / "overrides.csv"))

    for t in txns:
        info = accounts.setdefault(t.account, AccountInfo(t.account, t.account_type, {t.source}))
        info.type = info.type or t.account_type
        info.count += 1
        info.first = min(info.first or t.date, t.date)
        info.last = max(info.last or t.date, t.date)
    for b in balances:
        accounts.setdefault(b.account, AccountInfo(b.account, "balance only", {"balances"}))

    return Dataset(txns, balances, w2, accounts, warnings)


LEDGER_FIELDS = ["date", "account", "merchant", "description", "amount", "category", "kind", "id", "source"]


def write_ledger(ds: Dataset, path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(LEDGER_FIELDS)
        for t in ds.txns:
            w.writerow([t.date, t.account, t.merchant, t.description, f"{t.amount:.2f}", t.category, t.kind, t.id,
                        t.source])
