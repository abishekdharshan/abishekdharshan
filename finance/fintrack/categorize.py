"""Turn raw rows into categorized transactions.

Precedence, highest first:
  1. overrides.csv   - per-transaction fixes, keyed by the id in ledger.csv
  2. rules.csv       - your rules
  3. importer preset - structured sources (Robinhood codes, Coinbase types, wallets)
  4. default_rules.csv
  5. the bank's own category column (Chase, Amex, Apple Card, ...)
  6. transfer matching - same amount leaving one account and arriving in another
  7. Uncategorized / Uncategorized Income / Refunds & Credits (card credits)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Optional

from .model import CATEGORIES, Txn

DEFAULT_RULES = Path(__file__).with_name("default_rules.csv")


@dataclass
class Rule:
    pattern: re.Pattern
    category: str
    merchant: str = ""
    direction: str = ""
    account: Optional[re.Pattern] = None
    account_type: str = ""

    def matches(self, t: Txn) -> bool:
        if self.direction == "in" and t.amount <= 0:
            return False
        if self.direction == "out" and t.amount >= 0:
            return False
        if self.account_type and t.account_type != self.account_type:
            return False
        if self.account and not self.account.search(t.account):
            return False
        return bool(self.pattern.search(t.description))


def _csv_lines(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [line for line in f if line.strip() and not line.lstrip().startswith("#")]


def load_rules(path: Path) -> tuple[list[Rule], list[str]]:
    rules, problems = [], []
    if not path.exists():
        return rules, problems
    for n, row in enumerate(csv.DictReader(_csv_lines(path)), start=1):
        pattern = (row.get("pattern") or "").strip()
        category = (row.get("category") or "").strip()
        if not pattern or not category:
            continue
        try:
            compiled = re.compile(pattern, re.I)
        except re.error as e:
            problems.append(f"{path.name} rule {n}: bad pattern {pattern!r}: {e}")
            continue
        acct = (row.get("account") or "").strip()
        rule = Rule(compiled, category, (row.get("merchant") or "").strip(),
                    (row.get("direction") or "").strip().lower())
        if acct.lower().startswith("type:"):
            rule.account_type = acct[5:].strip().lower()
        elif acct:
            rule.account = re.compile(acct, re.I)
        rules.append(rule)
    return rules, problems


def load_overrides(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["id"].strip(): row for row in csv.DictReader(_csv_lines(path)) if (row.get("id") or "").strip()}


# Bank-provided categories (Chase, Amex, Apple Card, Capital One, Discover...)
_BANK_MAP = [
    (r"payment|autopay", "Credit Card Payment"),
    (r"grocer|supermarket", "Groceries"),
    (r"restaurant|food|dining|bar|coffee|fast food", "Dining & Drinks"),
    (r"airline|air travel|lodging|hotel|travel|car rental", "Travel"),
    (r"gas|fuel|automotive|transportation|taxi|parking|toll|rideshare", "Transport"),
    (r"utilit|bills", "Utilities"),
    (r"phone|internet|cable|communication", "Phone & Internet"),
    (r"health|medical|pharmac|drug|fitness", "Health & Fitness"),
    (r"entertainment|recreation", "Entertainment"),
    (r"education", "Education"),
    (r"gift|donation|charit", "Gifts & Donations"),
    (r"insurance", "Insurance"),
    (r"fee|interest|adjustment", "Fees & Interest"),
    (r"personal", "Personal Care"),
    (r"shopping|merchandise|retail|home|clothing|electronics|department|wholesale|warehouse", "Shopping"),
    (r"professional|business|services|other|miscellaneous", "Other Spending"),
]


def bank_category(raw: str, t: Txn) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw in CATEGORIES:
        return raw
    for pattern, category in _BANK_MAP:
        if re.search(pattern, raw, re.I):
            if category == "Credit Card Payment" and t.amount < 0:
                return ""
            return category
    return ""


# Merchant display names -------------------------------------------------------

_ALIASES = [
    (r"UBER ?EATS", "Uber Eats"), (r"\bUBER\b", "Uber"), (r"\bLYFT\b", "Lyft"),
    (r"AMZN MKTP|AMAZON\.COM|AMZN\.COM|AMAZON MKTPL|AMAZON MARK", "Amazon"), (r"AMAZON PRIME|AMZN PRIME", "Amazon Prime"),
    (r"WHOLEFDS|WHOLE FOODS", "Whole Foods"), (r"TRADER JOE", "Trader Joe's"), (r"STARBUCKS", "Starbucks"),
    (r"DOORDASH|\bDD \*", "DoorDash"), (r"APPLE\.COM/BILL|APPLE\.COM BILL", "Apple (subscriptions)"),
    (r"\bMTA\b|NYCT|OMNY", "MTA"), (r"GUSTO", "Gusto payroll"), (r"ZELLE", "Zelle"), (r"VENMO", "Venmo"),
    (r"NETFLIX", "Netflix"), (r"SPOTIFY", "Spotify"), (r"CITI ?BIKE", "Citi Bike"), (r"CON ?ED\b|CONSOLIDATED EDISON", "Con Edison"),
    (r"\bATM\b.*WITHDRWL|ATM WITHDRAWAL", "ATM withdrawal"), (r"IRS TREAS|IRS USATAXPYMT", "IRS"),
    (r"Online Banking payment to CRD|PAYMENT - THANK YOU|AUTOPAY PAYMENT|AUTOMATIC PAYMENT", "Card payment"),
]
_ALIASES = [(re.compile(p, re.I), name) for p, name in _ALIASES]

_PREFIXES = re.compile(
    r"^(CHECKCARD \d{4}|PURCHASE \d{4}|PURCHASE AUTHORIZED ON \d\d/\d\d|POS PURCHASE|DEBIT CARD PURCHASE|"
    r"POS DEBIT|RECURRING PAYMENT AUTHORIZED ON \d\d/\d\d|PMNT SENT|RECURRING|ACH (DEBIT|CREDIT)|"
    r"SQ ?\*|TST ?\*|SP ?\*|PAYPAL ?\*|PP ?\*|IC ?\*|BT ?\*|DNH ?\*|LS ?\*|GOOGLE ?\*)\s*", re.I)


def clean_merchant(desc: str) -> str:
    for pattern, name in _ALIASES:
        if pattern.search(desc):
            return name
    s = re.sub(r"\s+", " ", desc.upper()).strip()
    for _ in range(3):
        s = _PREFIXES.sub("", s)
    s = re.split(r" DES:| ID:| INDN:| CO ID:| CONF#| CONFIRMATION#", s)[0]
    s = re.split(r"\*|#|\d{4,}|\s\d{2}/\d{2}\b|\.COM\b", s)[0]
    s = re.sub(r"\s(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|"
               r"T[NX]|UT|V[AT]|W[AIVY]|PT|GB|UK|FR|ES|DE|IT|MX|CAN?)$", "", s.strip())
    s = _CITY_SUFFIX.sub("", s)
    s = re.sub(r"[^A-Z0-9&' .-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return " ".join(w.capitalize() for w in s.split()) if s else desc.strip()[:40]


_CITY_SUFFIX = re.compile(
    r"\s(NEW YORK|NEWYORK|BROOKLYN|QUEENS|BRONX|LONG ISLAND CITY|JERSEY CITY|HOBOKEN|SAN FRANCISCO|LOS ANGELES|"
    r"SANTA MONICA|OAKLAND|SEATTLE|CHICAGO|BOSTON|AUSTIN|MIAMI|DENVER|WASHINGTON|PHILADELPHIA|ATLANTA|DALLAS|HOUSTON|"
    r"PORTLAND|SAN DIEGO|SAN JOSE|PALO ALTO|LAS VEGAS|LONDON|PARIS|LISBOA|LISBON|BERLIN|TORONTO|MEXICO CITY)$")


# Transfer matching ------------------------------------------------------------

def _days(a: str, b: str) -> int:
    return abs((Date.fromisoformat(a) - Date.fromisoformat(b)).days)


def match_transfers(txns: list[Txn], window_days: int = 5) -> int:
    """Pair uncategorized rows where the same amount leaves one account and
    lands in another within a few days (e.g. a card payment whose description
    no rule knows). Both sides become "Transfer". Returns pairs matched."""
    open_rows = [t for t in txns if not t.category and abs(t.amount) >= 1]
    by_amount: dict[int, list[Txn]] = {}
    for t in open_rows:
        by_amount.setdefault(round(t.amount * 100), []).append(t)
    pairs = 0
    for t in sorted(open_rows, key=lambda t: t.date):
        if t.category or t.amount >= 0:
            continue
        candidates = [c for c in by_amount.get(round(-t.amount * 100), [])
                      if not c.category and c.account != t.account and _days(c.date, t.date) <= window_days]
        if candidates:
            other = min(candidates, key=lambda c: _days(c.date, t.date))
            t.category = other.category = "Transfer"
            pairs += 1
    return pairs


def categorize(txns: list[Txn], user_rules: list[Rule], default_rules: list[Rule], overrides: dict) -> None:
    for t in txns:
        preset, t.category = t.category, ""
        merchant = ""
        ov = overrides.get(t.id)
        if ov and (ov.get("category") or "").strip():
            t.category = ov["category"].strip()
        if not t.category:
            rule = next((r for r in user_rules if r.matches(t)), None)
            if rule:
                t.category, merchant = rule.category, rule.merchant
        if not t.category and preset:
            t.category = preset
        if not t.category:
            rule = next((r for r in default_rules if r.matches(t)), None)
            if rule:
                t.category, merchant = rule.category, rule.merchant
        if not t.category:
            t.category = bank_category(t.bank_category, t)
        if ov and (ov.get("merchant") or "").strip():
            merchant = ov["merchant"].strip()
        t.merchant = merchant or (t.merchant if t.source in ("apple_card", "robinhood", "coinbase", "zerion") and t.merchant
                                  else clean_merchant(t.description))

    match_transfers(txns)

    for t in txns:
        if t.category:
            continue
        if t.amount < 0:
            t.category = "Uncategorized"
        elif t.account_type == "credit":
            t.category = "Refunds & Credits"  # a credit on a card that isn't a payment
        else:
            t.category = "Uncategorized Income"
