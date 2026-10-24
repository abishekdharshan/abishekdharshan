from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional

INCOME, EXPENSE, TRANSFER, INVESTMENT = "income", "expense", "transfer", "investment"

# Category -> kind. Only "income" and "expense" count toward earned/spent;
# "transfer" and "investment" are money moving between your own accounts.
# Dict order is the display order. A category name not listed here (e.g. one
# you invent in rules.csv) is treated as spending.
CATEGORIES = {
    "Salary": INCOME,
    "Bonus & Other Income": INCOME,
    "Interest & Dividends": INCOME,
    "Crypto Rewards": INCOME,
    "Uncategorized Income": INCOME,
    "Rent & Housing": EXPENSE,
    "Utilities": EXPENSE,
    "Phone & Internet": EXPENSE,
    "Groceries": EXPENSE,
    "Dining & Drinks": EXPENSE,
    "Transport": EXPENSE,
    "Travel": EXPENSE,
    "Shopping": EXPENSE,
    "Subscriptions": EXPENSE,
    "Health & Fitness": EXPENSE,
    "Personal Care": EXPENSE,
    "Entertainment": EXPENSE,
    "Education": EXPENSE,
    "Gifts & Donations": EXPENSE,
    "Insurance": EXPENSE,
    "Taxes": EXPENSE,
    "Fees & Interest": EXPENSE,
    "Cash & ATM": EXPENSE,
    "P2P Payments": EXPENSE,
    "Refunds & Credits": EXPENSE,
    "Other Spending": EXPENSE,
    "Uncategorized": EXPENSE,
    "Credit Card Payment": TRANSFER,
    "Transfer": TRANSFER,
    "Investment Transfer": TRANSFER,
    "Crypto Transfer": TRANSFER,
    "Ignore": TRANSFER,
    "Investment Trade": INVESTMENT,
}

UNCATEGORIZED = ("Uncategorized", "Uncategorized Income")


def kind_of(category: str) -> str:
    return CATEGORIES.get(category, EXPENSE)


@dataclass
class Txn:
    date: str  # YYYY-MM-DD
    account: str  # folder name under raw/, e.g. "BofA Checking"
    description: str  # raw description from the export
    amount: float  # USD; positive = money in, negative = money out
    source: str  # importer that produced it
    account_type: str = "checking"  # checking | savings | credit | brokerage | crypto | wallet | manual
    category: str = ""  # importer preset first, final category after categorize()
    merchant: str = ""
    bank_category: str = ""  # category column from the export, if any
    balance: Optional[float] = None  # running balance after this row, if the export has one
    id: str = ""

    @property
    def kind(self) -> str:
        return kind_of(self.category)


@dataclass
class Balance:
    date: str
    account: str
    balance: float


def norm_desc(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def txn_key(t: Txn) -> str:
    return f"{t.account}|{t.date}|{t.amount:.2f}|{norm_desc(t.description).upper()}"


def assign_ids(txns: list[Txn]) -> None:
    """Give each row of ONE file a stable id.

    Identical rows within a file (two $5 coffees on the same day) get distinct
    occurrence numbers, so they survive; the same row repeated in an
    overlapping export of the same account maps to the same id and is
    de-duplicated.
    """
    seen: dict[str, int] = {}
    for t in txns:
        key = txn_key(t)
        n = seen.get(key, 0)
        seen[key] = n + 1
        t.id = hashlib.sha1(f"{key}|{n}".encode()).hexdigest()[:12]
