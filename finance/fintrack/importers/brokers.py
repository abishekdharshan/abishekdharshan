"""Robinhood (brokerage activity report) and Coinbase (transaction history) CSVs.

Both carry a transaction code, so they arrive pre-categorized: buys and sells
are investment trades (not spending), deposits are transfers from your bank,
dividends and staking rewards are income.
"""

from __future__ import annotations

import re
from typing import Optional

from ..model import Txn
from .common import find_header, parse_date, parse_money, records

# --- Robinhood ---------------------------------------------------------------

ROBINHOOD_REQUIRED = {"activity date", "instrument", "description", "trans code", "amount"}

_RH_TRANSFER = {"ACH", "XENT", "XENT_CC", "ACATI", "ACATO", "ITRF", "WIRE", "FUTSWP", "IADJ", "OCA"}
_RH_INCOME = {"CDIV", "MDIV", "QDIV", "DIV", "INT", "SLIP", "DIVNRA"}
_RH_BONUS = {"GDBP", "GMPC", "REWARD", "MISC", "T/A", "REC"}
_RH_TAX = {"DTAX", "NRA", "FTAX"}
_RH_FEE = {"AFEE", "DFEE", "MINT", "MRGC", "ADRF", "SECFEE"}
_RH_TRADE = {"BUY", "SELL", "BTO", "BTC", "STO", "STC", "OEXP", "OASGN", "OEXCS", "SPL", "SPR", "CONV", "MRGS",
             "SXCH", "CIL", "SOFF", "BCXL", "SCXL", "DCF"}


def robinhood_category(code: str, instrument: str, desc: str = "") -> str:
    if code == "ACH" and not re.fullmatch(r"ACH (Deposit|Withdrawal)", desc.strip(), re.I):
        return ""  # e.g. a paycheck direct-deposited into Robinhood: let the rules decide
    if code in _RH_TRANSFER:
        return "Investment Transfer"
    if code in _RH_INCOME:
        return "Interest & Dividends"
    if code in _RH_BONUS:
        return "Bonus & Other Income"
    if code == "GOLD":
        return "Subscriptions"
    if code in _RH_TAX:
        return "Taxes"
    if code in _RH_FEE:
        return "Fees & Interest"
    if code in _RH_TRADE or instrument:
        return "Investment Trade"
    return ""  # unknown cash movement: surfaces under "Needs a category"


def parse_robinhood(rows, header_idx: int, account: str, opts: dict):
    txns = []
    for rec in records(rows, header_idx):
        date = parse_date(rec.get("activity date"))
        amount = parse_money(rec.get("amount"))
        if not date or not amount:
            continue  # disclaimer rows at the end; zero-cash rows (splits, transfers of shares)
        code = rec.get("trans code", "").strip().upper()
        instrument = rec.get("instrument", "").strip()
        desc = " ".join(rec.get("description", "").split())
        txns.append(Txn(
            date=date, account=account, amount=amount, source="robinhood",
            description=f"{instrument + ' ' if instrument else ''}{desc} [{code}]",
            account_type=opts.get("type") or "brokerage",
            category=robinhood_category(code, instrument, desc),
            merchant="Robinhood" + (f" {instrument}" if instrument else ""),
        ))
    return txns, []


# --- Coinbase ----------------------------------------------------------------

COINBASE_REQUIRED = {"timestamp", "transaction type", "asset", "quantity transacted"}


def _col(rec: dict, *names: str) -> Optional[str]:
    for n in names:
        if rec.get(n):
            return rec[n]
    return None


def coinbase_category(typ: str) -> tuple[str, int]:
    """(category, direction) for a Coinbase transaction type; direction 0 = use the quantity sign."""
    t = typ.lower()
    if "buy" in t:
        return "Investment Trade", -1
    if "sell" in t:
        return "Investment Trade", 1
    if t.startswith("convert"):
        return "Investment Trade", -1
    if t in ("deposit", "fiat deposit"):
        return "Investment Transfer", 1
    if t in ("withdrawal", "fiat withdrawal"):
        return "Investment Transfer", -1
    if t == "send":
        return "Crypto Transfer", -1
    if t == "receive":
        return "Crypto Transfer", 1
    if any(w in t for w in ("reward", "staking income", "earn", "inflation", "interest", "airdrop", "incentive")):
        return "Crypto Rewards", 1
    if any(w in t for w in ("pro ", "exchange ", "staking transfer", "unstaking", "wrap", "unwrap")):
        return "Crypto Transfer", 0
    if "subscription" in t:
        return "Subscriptions", -1
    return "", 0


def parse_coinbase(rows, header_idx: int, account: str, opts: dict):
    txns = []
    for rec in records(rows, header_idx):
        date = parse_date(rec.get("timestamp"))
        if not date:
            continue
        typ = rec.get("transaction type", "")
        asset = rec.get("asset", "")
        qty = parse_money(rec.get("quantity transacted")) or 0.0
        price = parse_money(_col(rec, "price at transaction", "spot price at transaction",
                                 "usd spot price at transaction")) or 0.0
        total = parse_money(_col(rec, "total (inclusive of fees and/or spread)", "usd total (inclusive of fees)",
                                 "total (inclusive of fees)"))
        subtotal = parse_money(_col(rec, "subtotal", "usd subtotal"))
        usd = abs(total or subtotal or (qty * price) or (qty if asset.upper() in ("USD", "USDC") else 0))
        category, direction = coinbase_category(typ)
        if direction == 0:
            direction = -1 if qty < 0 else 1
        if category == "Crypto Rewards":
            usd = abs(subtotal or qty * price or usd)  # value of the reward, before any fee
        if not usd:
            continue
        notes = rec.get("notes", "")
        txns.append(Txn(
            date=date, account=account, amount=direction * usd, source="coinbase",
            description=f"{typ} {abs(qty):g} {asset}" + (f" - {notes}" if notes else ""),
            account_type=opts.get("type") or "crypto",
            category=category,
            merchant=f"Coinbase {asset}".strip(),
        ))
    return txns, []


def detect_robinhood(rows) -> Optional[int]:
    return find_header(rows, ROBINHOOD_REQUIRED)


def detect_coinbase(rows) -> Optional[int]:
    return find_header(rows, COINBASE_REQUIRED)


# --- Charles Schwab brokerage ------------------------------------------------

SCHWAB_REQUIRED = {"date", "action", "symbol", "description", "quantity", "price", "amount"}

_SCHWAB_INCOME = re.compile(r"dividend|div reinvest|\bdiv\b|interest|cap gain|distribution", re.I)
_SCHWAB_TRANSFER = re.compile(r"moneylink|funds received|funds paid|wire|journal|transfer|deposit|withdrawal", re.I)
_SCHWAB_FEE = re.compile(r"fee|margin interest", re.I)
_SCHWAB_TAX = re.compile(r"tax", re.I)


def schwab_category(action: str, symbol: str) -> str:
    if _SCHWAB_TAX.search(action):
        return "Taxes"
    if _SCHWAB_FEE.search(action):
        return "Fees & Interest"
    if _SCHWAB_INCOME.search(action) and "reinvest shares" not in action.lower():
        return "Interest & Dividends"
    if _SCHWAB_TRANSFER.search(action):
        return "Investment Transfer"
    if symbol or re.search(r"buy|sell|reinvest|split|expired|assigned|exercise|spin|lieu|exchange", action, re.I):
        return "Investment Trade"
    return ""


def parse_schwab(rows, header_idx: int, account: str, opts: dict):
    txns = []
    for rec in records(rows, header_idx):
        date = parse_date(rec.get("date", "").split(" as of")[0])
        amount = parse_money(rec.get("amount"))
        if not date or not amount:
            continue
        action, symbol = rec.get("action", ""), rec.get("symbol", "")
        desc = " ".join(rec.get("description", "").split())
        txns.append(Txn(
            date=date, account=account, amount=amount, source="schwab",
            description=f"{action}: {symbol + ' ' if symbol else ''}{desc}",
            account_type=opts.get("type") or "brokerage",
            category=schwab_category(action, symbol),
            merchant="Schwab" + (f" {symbol}" if symbol else ""),
        ))
    return txns, []


def detect_schwab(rows) -> Optional[int]:
    return find_header(rows, SCHWAB_REQUIRED)
