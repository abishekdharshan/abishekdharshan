"""Aggregate the ledger and write the HTML report + a terminal summary."""

from __future__ import annotations

import bisect
import json
from collections import defaultdict
from datetime import date as Date
from pathlib import Path

from .ledger import Dataset
from .model import CATEGORIES, EXPENSE, INCOME, UNCATEGORIZED, kind_of

TEMPLATE = Path(__file__).with_name("report_template.html")


def _months(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= last[:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _month_end(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    nxt = Date(y + 1, 1, 1) if m == 12 else Date(y, m + 1, 1)
    return Date.fromordinal(nxt.toordinal() - 1).isoformat()


def monthly_networth(ds: Dataset):
    per_acct: dict[str, dict[str, float]] = defaultdict(dict)
    for b in ds.balances:
        per_acct[b.account][b.date] = b.balance  # same-day rows: the last one is the end-of-day balance
    if not per_acct:
        return None
    series = {a: sorted(d.items()) for a, d in per_acct.items()}
    first = min(s[0][0] for s in series.values())
    last = max(s[-1][0] for s in series.values())
    months = _months(first, last)
    accounts = {}
    for acct, pts in series.items():
        dates = [d for d, _ in pts]
        vals = []
        for m in months:
            i = bisect.bisect_right(dates, _month_end(m)) - 1
            vals.append(round(pts[i][1], 2) if i >= 0 else None)
        accounts[acct] = vals
    total = [round(sum(v[i] or 0 for v in accounts.values()), 2) for i in range(len(months))]
    return {"months": months, "total": total, "accounts": accounts}


def report_data(ds: Dataset, generated: str) -> dict:
    acct_names = sorted(ds.accounts)
    acct_idx = {a: i for i, a in enumerate(acct_names)}
    cats = list(CATEGORIES) + sorted({t.category for t in ds.txns} - set(CATEGORIES))
    cat_idx = {c: i for i, c in enumerate(cats)}
    return {
        "generated": generated,
        "accounts": [{
            "name": a.name, "type": a.type, "formats": sorted(a.formats), "files": a.files,
            "count": a.count, "first": a.first, "last": a.last,
        } for a in (ds.accounts[n] for n in acct_names)],
        "categories": [{"name": c, "kind": kind_of(c)} for c in cats],
        "txns": [[t.date, acct_idx[t.account], t.merchant, t.description, round(t.amount, 2), cat_idx[t.category], t.id]
                 for t in ds.txns],
        "networth": monthly_networth(ds),
        "w2": sorted(ds.w2, key=lambda r: r["year"]),
        "warnings": ds.warnings,
    }


def write_html(data: dict, out: Path) -> None:
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", payload)
    out.write_text(html)


# --- terminal summary ----------------------------------------------------------

def _money(v: float) -> str:
    return f"-${-v:,.0f}" if v < 0 else f"${v:,.0f}"


def yearly(ds: Dataset) -> list[dict]:
    rows: dict[str, dict] = {}
    for t in ds.txns:
        k = t.kind
        if k not in (INCOME, EXPENSE):
            continue
        r = rows.setdefault(t.date[:4], {"year": t.date[:4], "earned": 0.0, "spent": 0.0, "months": set()})
        r["months"].add(t.date[:7])
        if k == INCOME:
            r["earned"] += t.amount
        else:
            r["spent"] -= t.amount
    return [rows[y] for y in sorted(rows)]


def uncategorized(ds: Dataset, limit: int = 15) -> list[tuple[str, int, float, str]]:
    groups: dict[str, list] = {}
    for t in ds.txns:
        if t.category in UNCATEGORIZED:
            g = groups.setdefault(t.merchant, [0, 0.0, t.description, t.account])
            g[0] += 1
            g[1] += t.amount
    ranked = sorted(groups.items(), key=lambda kv: -abs(kv[1][1]))
    return [(m, g[0], g[1], f"{g[3]}: {g[2]}") for m, g in ranked[:limit]]


def print_summary(ds: Dataset, log=print) -> None:
    log("")
    log(f"{'Account':34} {'Type':10} {'From':10}   {'To':10}  {'Txns':>6}")
    for a in sorted(ds.accounts.values(), key=lambda a: a.name):
        log(f"{a.name[:34]:34} {a.type[:10]:10} {a.first or '-':10} - {a.last or '-':10}  {a.count:6d}")
    log("")
    log(f"{'Year':6} {'Earned':>12} {'Spent':>12} {'Saved':>12} {'Rate':>6}  Months")
    for r in yearly(ds):
        saved = r["earned"] - r["spent"]
        rate = f"{saved / r['earned'] * 100:5.0f}%" if r["earned"] > 0 else "     -"
        log(f"{r['year']:6} {_money(r['earned']):>12} {_money(r['spent']):>12} {_money(saved):>12} {rate}  {len(r['months'])}")
    unc = uncategorized(ds)
    if unc:
        n = sum(1 for t in ds.txns if t.category in UNCATEGORIZED)
        log("")
        log(f"Needs a category ({n} transactions; biggest first - add rules to rules.csv):")
        for merchant, count, total, sample in unc[:10]:
            log(f"  {_money(total):>10}  {count:4d}x  {merchant[:30]:30}  e.g. {sample[:70]}")
    if ds.warnings:
        log("")
        log("Warnings:")
        for w in ds.warnings:
            log(f"  - {w}")
