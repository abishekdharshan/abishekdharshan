"""On-chain wallets via the Zerion API (https://developers.zerion.io).

`fintrack sync-wallets` downloads each wallet's transaction history and
portfolio-value chart into cache/zerion/. `build` reads only that cache, so
reports work offline and the API is hit only when you ask.

Defaults: sends/receives are "Crypto Transfer" and swaps are "Investment
Trade" (neither counts as earned or spent), claims are "Crypto Rewards", and
gas you paid is "Fees & Interest". Descriptions include the counterparty
address, so a rule like `from 0xabc...` -> Salary reclassifies crypto payroll.
"""

from __future__ import annotations

import base64
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..model import Balance, Txn

API = "https://api.zerion.io/v1"

_TRADE_OPS = {"trade", "deposit", "withdraw", "mint", "burn", "execute", "stake", "unstake"}


def load_wallets(data_dir: Path) -> list[tuple[str, str]]:
    path = data_dir / "wallets.csv"
    if not path.exists():
        return []
    out = []
    with open(path, newline="") as f:
        for row in csv.reader(line for line in f if not line.lstrip().startswith("#")):
            if not row or not row[0].strip() or row[0].strip().lower() == "address":
                continue
            addr = row[0].strip()
            label = row[1].strip() if len(row) > 1 and row[1].strip() else f"{addr[:6]}…{addr[-4:]}"
            out.append((addr, label))
    return out


def _get(url: str, api_key: str) -> dict:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}", "accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def sync(data_dir: Path, api_key: str, log=print) -> None:
    cache = data_dir / "cache" / "zerion"
    cache.mkdir(parents=True, exist_ok=True)
    for addr, label in load_wallets(data_dir):
        log(f"  {label} ({addr})")
        params = urllib.parse.urlencode({"currency": "usd", "page[size]": 100, "filter[trash]": "only_non_trash"})
        url = f"{API}/wallets/{addr}/transactions/?{params}"
        items = []
        while url:
            page = _get(url, api_key)
            items.extend(page.get("data", []))
            url = (page.get("links") or {}).get("next")
            log(f"    {len(items)} transactions", end="\r")
        log(f"    {len(items)} transactions")
        (cache / f"{addr.lower()}.transactions.json").write_text(json.dumps(items))
        chart = _get(f"{API}/wallets/{addr}/charts/max?currency=usd", api_key)
        (cache / f"{addr.lower()}.chart.json").write_text(json.dumps(chart))


def _qty(t: dict) -> float:
    q = t.get("quantity") or {}
    try:
        return float(q.get("float") if q.get("float") is not None else q.get("numeric") or 0)
    except (TypeError, ValueError):
        return 0.0


def _symbol(t: dict) -> str:
    info = t.get("fungible_info") or {}
    if info.get("symbol"):
        return info["symbol"]
    nft = t.get("nft_info") or {}
    return nft.get("name") or "NFT"


def parse_wallet(addr: str, label: str, items: list[dict], own: set[str]) -> list[Txn]:
    account = f"Wallet: {label}"
    me = addr.lower()
    txns = []
    for item in items:
        a = item.get("attributes") or {}
        if (a.get("flags") or {}).get("is_trash") or a.get("status") == "failed":
            continue
        mined = a.get("mined_at") or ""
        date = mined[:10]
        if len(date) != 10:
            continue
        op = a.get("operation_type") or "execute"
        chain = (((item.get("relationships") or {}).get("chain") or {}).get("data") or {}).get("id", "")
        transfers = a.get("transfers") or []
        value_in = sum(t.get("value") or 0 for t in transfers if t.get("direction") == "in")
        value_out = sum(t.get("value") or 0 for t in transfers if t.get("direction") == "out")
        legs = []
        for t in transfers:
            d = t.get("direction")
            if d not in ("in", "out"):
                continue
            who = t.get("sender") if d == "in" else t.get("recipient")
            leg = f"{'+' if d == 'in' else '-'}{_qty(t):g} {_symbol(t)}"
            if who and who.lower() != me:
                leg += f" {'from' if d == 'in' else 'to'} {who.lower()}"
            legs.append(leg)
        desc = f"{op}: {', '.join(legs) or 'contract call'} [{chain}]"
        amount = round(value_in - value_out, 2)

        counterparties = {((t.get("sender") if t.get("direction") == "in" else t.get("recipient")) or "").lower()
                          for t in transfers} - {"", me}
        if op in ("send", "receive"):
            category = "Crypto Transfer"
        elif op == "claim":
            category = "Crypto Rewards"
        elif op in _TRADE_OPS:
            category = "Investment Trade"
        else:
            category = "Crypto Transfer" if counterparties and counterparties <= own else "Investment Trade"
        if amount:
            txns.append(Txn(date=date, account=account, description=desc, amount=amount, source="zerion",
                            account_type="wallet", category=category, merchant=f"{op.title()} ({chain})"))

        fee = a.get("fee") or {}
        fee_value = fee.get("value") or 0
        if fee_value and (a.get("sent_from") or "").lower() == me:
            txns.append(Txn(date=date, account=account, description=f"gas: {op} [{chain}] {a.get('hash', '')}",
                            amount=-round(fee_value, 2), source="zerion", account_type="wallet",
                            category="Fees & Interest", merchant=f"Gas ({chain})"))
    return txns


def parse_chart(addr: str, label: str, chart: dict) -> list[Balance]:
    points = (((chart or {}).get("data") or {}).get("attributes") or {}).get("points") or []
    out = []
    for ts, value in points:
        if value is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        out.append(Balance(date, f"Wallet: {label}", float(value)))
    return out


def load_cached(data_dir: Path) -> tuple[list[list[Txn]], list[Balance], list[str]]:
    """Per-wallet transaction lists (each list gets its own ids), balances, warnings."""
    cache = data_dir / "cache" / "zerion"
    wallets = load_wallets(data_dir)
    own = {a.lower() for a, _ in wallets}
    groups, balances, warnings = [], [], []
    for addr, label in wallets:
        tx_path = cache / f"{addr.lower()}.transactions.json"
        if not tx_path.exists():
            warnings.append(f"Wallet {label}: not synced yet - run `python3 -m fintrack sync-wallets`")
            continue
        groups.append(parse_wallet(addr, label, json.loads(tx_path.read_text()), own))
        chart_path = cache / f"{addr.lower()}.chart.json"
        if chart_path.exists():
            balances.extend(parse_chart(addr, label, json.loads(chart_path.read_text())))
    return groups, balances, warnings
