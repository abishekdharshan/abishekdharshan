"""Bank and credit-card CSV exports.

Known layouts are listed in FORMATS; anything else with a date, a description
and an amount (or debit/credit) column goes through the generic importer.
Header names come from each institution's "download transactions -> CSV"
export. Banks change these occasionally; if a file is skipped or the signs
look inverted, see README "Troubleshooting".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..model import Balance, Txn
from .common import find_header, lower_cells, parse_date, parse_money, records


@dataclass
class BankFormat:
    name: str
    required: set
    date: str
    desc: str
    account_type: Optional[str]  # None = infer from the folder name
    amount: Optional[str] = None  # one signed column...
    debit: Optional[str] = None  # ...or separate debit / credit columns
    credit: Optional[str] = None
    flip: object = False  # True when purchases are positive; "auto" when unsure
    category: Optional[str] = None
    merchant: Optional[str] = None
    balance: Optional[str] = None
    extra: tuple = field(default_factory=tuple)


FORMATS = [
    BankFormat("bofa_checking", {"date", "description", "amount", "running bal."},
               "date", "description", "checking", amount="amount", balance="running bal."),
    BankFormat("bofa_credit", {"posted date", "reference number", "payee", "address", "amount"},
               "posted date", "payee", "credit", amount="amount"),
    BankFormat("chase_checking", {"details", "posting date", "description", "amount", "type", "balance"},
               "posting date", "description", "checking", amount="amount", balance="balance"),
    BankFormat("chase_credit", {"transaction date", "post date", "description", "category", "type", "amount"},
               "transaction date", "description", "credit", amount="amount", category="category"),
    BankFormat("amex", {"date", "description", "card member", "amount"},
               "date", "description", "credit", amount="amount", flip=True, category="category"),
    BankFormat("amex", {"date", "description", "amount", "appears on your statement as"},
               "date", "description", "credit", amount="amount", flip=True, category="category"),
    BankFormat("apple_card", {"transaction date", "clearing date", "description", "merchant", "category", "type", "amount (usd)"},
               "transaction date", "description", "credit", amount="amount (usd)", flip=True,
               category="category", merchant="merchant"),
    BankFormat("capital_one", {"transaction date", "posted date", "card no.", "description", "category", "debit", "credit"},
               "transaction date", "description", "credit", debit="debit", credit="credit", category="category"),
    BankFormat("citi", {"status", "date", "description", "debit", "credit"},
               "date", "description", "credit", debit="debit", credit="credit"),
    BankFormat("discover", {"trans. date", "post date", "description", "amount", "category"},
               "trans. date", "description", "credit", amount="amount", flip=True, category="category"),
    BankFormat("us_bank", {"date", "transaction", "name", "memo", "amount"},
               "date", "name", None, amount="amount", flip="auto"),
]

_CREDIT_NAME = re.compile(
    r"card|credit|visa|amex|master|sapphire|freedom|venture|platinum|altitude|double cash|custom cash|"
    r"premier|reserve|bilt|explorer|strata|travel rewards|unlimited cash|cash rewards|prime", re.I)


def account_type_for(folder: str, fmt_type: Optional[str], override: Optional[str]) -> str:
    if override:
        return override
    if fmt_type:
        if fmt_type == "checking" and re.search(r"sav", folder, re.I):
            return "savings"
        return fmt_type
    if _CREDIT_NAME.search(folder):
        return "credit"
    if re.search(r"sav", folder, re.I):
        return "savings"
    return "checking"


def _signed(rec: dict, fmt: BankFormat) -> Optional[float]:
    if fmt.amount:
        return parse_money(rec.get(fmt.amount))
    debit = parse_money(rec.get(fmt.debit))
    credit = parse_money(rec.get(fmt.credit))
    if debit is None and credit is None:
        return None
    # Debit = money out, credit = money in, whatever sign the bank wrote them with.
    return abs(credit or 0) - abs(debit or 0)


def _apply_sign(txns: list[Txn], flip, sign_opt: str) -> None:
    if sign_opt == "flip":
        do_flip = True
    elif sign_opt == "as-is":
        do_flip = False
    elif flip == "auto":
        do_flip = _mostly_positive(txns)
    else:
        do_flip = bool(flip)
    if do_flip:
        for t in txns:
            t.amount = -t.amount


def _mostly_positive(txns: list[Txn]) -> bool:
    # In any spending account most rows are money out. If most rows are
    # positive, the export writes purchases as positive numbers.
    nonzero = [t.amount for t in txns if t.amount]
    return bool(nonzero) and sum(a > 0 for a in nonzero) / len(nonzero) > 0.6


def detect_known(rows) -> Optional[tuple[BankFormat, int]]:
    for fmt in FORMATS:
        idx = find_header(rows, fmt.required)
        if idx is not None:
            return fmt, idx
    return None


def parse_known(rows, header_idx: int, fmt: BankFormat, account: str, opts: dict):
    acct_type = account_type_for(account, fmt.account_type, opts.get("type"))
    txns: list[Txn] = []
    balances: list[Balance] = []
    for rec in records(rows, header_idx):
        date = parse_date(rec.get(fmt.date))
        if not date:
            continue
        desc = rec.get(fmt.desc, "")
        for col in fmt.extra:
            if rec.get(col):
                desc = f"{desc} {rec[col]}"
        amount = _signed(rec, fmt)
        bal = parse_money(rec.get(fmt.balance)) if fmt.balance else None
        if amount is None:
            # BofA starts with "Beginning balance as of ..." and a blank amount.
            if bal is not None:
                balances.append(Balance(date, account, bal))
            continue
        txns.append(Txn(
            date=date, account=account, description=desc, amount=amount, source=fmt.name,
            account_type=acct_type,
            bank_category=rec.get(fmt.category, "") if fmt.category else "",
            merchant=rec.get(fmt.merchant, "") if fmt.merchant else "",
            balance=bal,
        ))
    _apply_sign(txns, fmt.flip, opts.get("sign", "auto"))
    for t in txns:
        if t.balance is not None:
            balances.append(Balance(t.date, account, t.balance))
    return txns, balances


# --- generic -----------------------------------------------------------------

_DATE_COLS = ["transaction date", "trans. date", "trans date", "date", "posted date", "posting date",
              "post date", "transaction_date", "date posted"]
_DESC_COLS = ["description", "payee", "merchant", "merchant name", "name", "transaction description",
              "details", "memo", "narrative", "transaction"]
_AMOUNT_COLS = ["amount", "amount (usd)", "transaction amount", "amount usd", "net amount", "value"]
_DEBIT_COLS = ["debit", "debits", "debit amount", "withdrawal", "withdrawals", "money out", "paid out"]
_CREDIT_COLS = ["credit", "credits", "credit amount", "deposit", "deposits", "money in", "paid in"]
_TYPE_COLS = ["type", "transaction type", "debit/credit", "credit/debit", "dr/cr"]
_BAL_COLS = ["balance", "running balance", "running bal.", "runningbalance", "available balance", "current balance"]


def _first(cells: list[str], names: list[str]) -> Optional[str]:
    for n in names:
        if n in cells:
            return n
    return None


def detect_generic(rows) -> Optional[tuple[int, dict]]:
    for i, row in enumerate(rows[:40]):
        cells = lower_cells(row)
        date = _first(cells, _DATE_COLS) or next((c for c in cells if "date" in c), None)
        desc = _first(cells, _DESC_COLS)
        amount = _first(cells, _AMOUNT_COLS)
        debit, credit = _first(cells, _DEBIT_COLS), _first(cells, _CREDIT_COLS)
        if date and desc and (amount or (debit and credit)):
            return i, {
                "date": date, "desc": desc, "amount": amount, "debit": debit, "credit": credit,
                "category": "category" if "category" in cells else None,
                "type": _first(cells, _TYPE_COLS),
                "balance": _first(cells, _BAL_COLS),
            }
    return None


_OUT_WORDS = re.compile(r"debit|\bdr\b|purchase|sale|withdraw|charge|fee|interest", re.I)
_IN_WORDS = re.compile(r"credit|\bcr\b|payment|refund|return|deposit|reward|cashback|cash back", re.I)


def parse_generic(rows, header_idx: int, cols: dict, account: str, opts: dict):
    fmt = BankFormat("generic", set(), cols["date"], cols["desc"], None,
                     amount=cols["amount"], debit=cols["debit"], credit=cols["credit"],
                     flip="auto", category=cols["category"], balance=cols["balance"])
    if fmt.amount is None:
        fmt.flip = False  # debit/credit columns already say which way money moved
    txns, balances = parse_known(rows, header_idx, fmt, account, {**opts, "sign": "as-is"})
    # Unsigned amounts plus a debit/credit "type" column -> sign from the type.
    type_col = cols["type"]
    recs = [r for r in records(rows, header_idx) if parse_date(r.get(fmt.date))]
    if fmt.amount and type_col and txns and all(t.amount >= 0 for t in txns) and len(recs) == len(txns):
        for t, rec in zip(txns, recs):
            typ = rec.get(type_col, "")
            if _OUT_WORDS.search(typ) and not _IN_WORDS.search(typ):
                t.amount = -abs(t.amount)
        return txns, balances
    _apply_sign(txns, fmt.flip, opts.get("sign", "auto"))
    return txns, balances


# --- Wells Fargo: no header row; date, amount, "*", check number, description --

def is_wells_fargo(rows) -> bool:
    data = [r for r in rows if any(c.strip() for c in r)][:5]
    return bool(data) and all(len(r) == 5 and parse_date(r[0]) and parse_money(r[1]) is not None and r[2].strip() == "*"
                              for r in data)


def parse_wells_fargo(rows, account: str, opts: dict):
    acct_type = account_type_for(account, None, opts.get("type"))
    txns = [Txn(date=parse_date(r[0]), account=account, description=r[4], amount=parse_money(r[1]),
                source="wells_fargo", account_type=acct_type)
            for r in rows if len(r) == 5 and parse_date(r[0]) and parse_money(r[1]) is not None]
    return txns, []
