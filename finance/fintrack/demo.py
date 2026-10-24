"""Sample data for a fictional person, written in each institution's real
export layout so `fintrack demo` exercises the same importers as real files."""

from __future__ import annotations

import csv
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

GROSS = {2022: 95000, 2023: 112000, 2024: 135000, 2025: 158000, 2026: 176000}
RENT = {2022: 2650, 2023: 2900, 2024: 2900, 2025: 3300, 2026: 3300}
START, END = date(2022, 1, 1), date(2026, 9, 30)
WALLET = "0x1111111111111111111111111111111111111111"


def _days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def generate(out: Path) -> None:
    rnd = random.Random(7)
    if out.exists():
        shutil.rmtree(out)
    raw = out / "raw"
    checking: list[tuple[date, str, float]] = []
    cards: dict[str, list[tuple[date, str, float]]] = {"bofa": [], "chase": [], "amex": []}
    robinhood: list[list[str]] = []
    coinbase: list[list[str]] = []

    def card_for(d: date) -> str:
        if d < date(2023, 4, 1):
            return "bofa"
        if d < date(2024, 2, 1):
            return "chase"
        return "amex" if rnd.random() < 0.55 else "chase"

    def spend(d: date, desc: str, amount: float, card: str = "") -> None:
        cards[card or card_for(d)].append((d, desc, -round(amount, 2)))

    for d in _days():
        y, dom = d.year, d.day
        last_dom = ((d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        # Paychecks on the 15th and the last day of the month.
        if dom in (15, last_dom):
            net = GROSS[y] * 0.655 / 24 + rnd.uniform(-15, 15)
            checking.append((d, f"GUSTO DES:PAY {d:%y%m%d} ID:XXXXX81234 INDN:DOE,ALEX CO ID:XXXXX45678 PPD", round(net, 2)))
        if d.month == 3 and dom == 15 and y in (2024, 2025, 2026):
            checking.append((d, f"GUSTO DES:PAY BONUS ID:XXXXX81234 INDN:DOE,ALEX PPD", round(GROSS[y] * 0.1 * 0.6, 2)))
        if dom == 1:
            checking.append((d, f"BILT DES:RENT PAYMT ID:{rnd.randint(10**8, 10**9)} INDN:ALEX DOE WEB", -RENT[y]))
            checking.append((d, "ROBINHOOD DES:FUNDS ID:5RH8213 INDN:ALEX DOE WEB", -(500 + 250 * (y - 2022))))
            robinhood.append(["ACH", d, "", "ACH Deposit", "", "", 500 + 250 * (y - 2022)])
            for tick, price in (("VTI", 200 + 15 * (y - 2022) + rnd.uniform(-8, 8)), ("AAPL", 150 + 20 * (y - 2022) + rnd.uniform(-10, 10))):
                spend_amt = (500 + 250 * (y - 2022)) / 2
                robinhood.append(["Buy", d + timedelta(days=1), tick, f"{tick} Market Buy", round(spend_amt / price, 4), round(price, 2), -spend_amt])
        if dom == 3:
            checking.append((d, f"CON ED OF NY DES:INTELL CK ID:{rnd.randint(10**8, 10**9)} INDN:ALEX DOE WEB",
                             -round(70 + 60 * (d.month in (1, 2, 7, 8)) + rnd.uniform(0, 30), 2)))
            spend(d, "VERIZON*RECURRING PAY 800-922-0204 FL", 85)
        if dom == 20 and d.month in (1, 4, 7, 10):
            robinhood.append(["CDIV", d, "VTI", "Cash Div: R/D Q", "", "", round(20 + 12 * (y - 2022) + rnd.uniform(0, 5), 2)])
        if dom == 2 and y >= 2024:
            robinhood.append(["GOLD", d, "", "Gold Subscription Fee", "", "", -5.0])
        if dom == 10 and d.month % 3 == 1:
            amt = 1000 if y < 2025 else 1500
            checking.append((d, f"COINBASE INC. DES:8889087930 ID:XXXXXX INDN:ALEX DOE CO ID:XXXXX WEB", -amt))
            coinbase.append([d, "Deposit", "USD", amt, 1, amt, amt, 0, f"Deposit from Bank of America"])
            for asset, px in (("BTC", 30000 + 9000 * (y - 2022)), ("ETH", 1800 + 400 * (y - 2022))):
                usd = amt / 2
                coinbase.append([d + timedelta(days=1), "Buy", asset, round(usd / px, 6), px, usd - 7.5, usd, 7.5, f"Bought {asset}"])
        if dom == 28:
            coinbase.append([d, "Staking Income", "ETH", 0.004, 1800 + 400 * (y - 2022), 0, 0, 0, ""])
        if d == date(2024, 3, 20):
            coinbase.append([d, "Send", "ETH", -1.5, 3000, 4500, 4500, 0, f"Sent 1.5 ETH to {WALLET}"])
        if dom == 25:
            checking.append((d, "BKOFAMERICA ATM 06/25 #000003421 WITHDRWL 1290 BROADWAY NEW YORK NY", -rnd.choice((60, 80, 100))))
            checking.append((d, "Interest Earned", round(rnd.uniform(0.3, 1.2), 2)))
        if d.month == 4 and dom == 12 and y <= 2025:
            checking.append((d, "IRS TREAS 310 DES:TAX REF ID:XXXXXX INDN:DOE ALEX", round(rnd.uniform(600, 1800), 2)))
        if rnd.random() < 0.06:
            name = rnd.choice(("SAM", "PRIYA", "JORDAN", "MAYA"))
            amt = round(rnd.uniform(20, 90), 2)
            if rnd.random() < 0.5:
                checking.append((d, f"Zelle payment to {name} for \"dinner\"; Conf# {rnd.randint(10**8, 10**9)}", -amt))
            else:
                checking.append((d, f"Zelle payment from {name} for \"split\"; Conf# {rnd.randint(10**8, 10**9)}", amt))
        if d == date(2023, 11, 6):
            checking.append((d, "WIRE TYPE:INTL IN DATE:231106 TIME:0912 ET TRN:2023110600123 SNDR REF:GIFT", 2000.0))

        # Card spending
        scale = 1 + 0.07 * (y - 2022)
        for p, desc, lo, hi in (
            (0.27, "WHOLEFDS MKT 10234 NEW YORK NY", 30, 120), (0.12, "TRADER JOE S #540 NEW YORK NY", 25, 80),
            (0.45, "STARBUCKS STORE 12345 NEW YORK NY", 5, 8), (0.30, "TST* JOE'S PIZZA NEW YORK NY", 12, 45),
            (0.18, "SWEETGREEN BLEECKER NEW YORK NY", 14, 19), (0.12, "DOORDASH*THAI VILLA SAN FRANCISCO CA", 25, 60),
            (0.10, "UBER *TRIP HELP.UBER.COM CA", 14, 42), (0.25, "MTA*NYCT PAYGO NEW YORK NY", 2.9, 2.9),
            (0.12, "AMZN Mktp US*2K3LJ4 Amzn.com/bill WA", 15, 140), (0.03, "UNIQLO USA 5TH AVE NEW YORK NY", 40, 160),
            (0.04, "THE BOWERY BALLROOM NEW YORK NY", 30, 90), (0.03, "CVS/PHARMACY #10023 NEW YORK NY", 8, 40),
            (0.035, "SQ *THE LOCAL SPOT BROOKLYN NY", 9, 30),
        ):
            if rnd.random() < p:
                spend(d, desc, rnd.uniform(lo, hi) * scale)
        if dom == 7:
            for desc, amt in (("NETFLIX.COM 866-579-7172 CA", 15.49), ("SPOTIFY USA 877-778-1161 NY", 11.99),
                              ("APPLE.COM/BILL 866-712-7753 CA", 2.99)):
                spend(d, desc, amt)
            if d >= date(2023, 3, 1):
                spend(d, "OPENAI *CHATGPT SUBSCR OPENAI.COM CA", 20)
            if y >= 2024:
                spend(d, "EQUINOX #142 NEW YORK NY", 285)
        if rnd.random() < 0.012:
            spend(d, "AMZN Mktp US*RF9K2 Amzn.com/bill WA", -round(rnd.uniform(20, 80), 2))  # refund
        # Trips: a long weekend in spring, summer and winter
        if (d.month, dom) in ((4, 2), (7, 10), (12, 15)):
            spend(d, "DELTA AIR 0062341234567 DELTA.COM GA", rnd.uniform(320, 650) * scale)
            spend(d + timedelta(days=1), "AIRBNB * HM2K4N3 AIRBNB.COM CA", rnd.uniform(500, 1400) * scale)
            for i in range(3):
                spend(d + timedelta(days=10 + i), "TST* LA COCINA LISBOA PT", rnd.uniform(30, 90))

    # Pay each card in full on the 20th for last month's purchases.
    pay_desc = {"bofa": ("Online Banking payment to CRD 4521 Confirmation# {n}", "PAYMENT - THANK YOU"),
                "chase": ("CHASE CREDIT CRD DES:AUTOPAY ID:{n} INDN:ALEX DOE PPD", "AUTOMATIC PAYMENT - THANK"),
                "amex": ("AMERICAN EXPRESS DES:ACH PMT ID:{n} INDN:ALEX DOE WEB", "AUTOPAY PAYMENT - THANK YOU")}
    for card, rows in cards.items():
        by_month: dict[tuple[int, int], float] = {}
        for d, _, amt in rows:
            by_month[(d.year, d.month)] = by_month.get((d.year, d.month), 0) + amt
        for (yy, mm), total in sorted(by_month.items()):
            pay_day = date(yy + (mm == 12), 1 if mm == 12 else mm + 1, 20)
            if pay_day > END or total >= 0:
                continue
            n = rnd.randint(10**9, 10**10)
            checking.append((pay_day, pay_desc[card][0].format(n=n), round(total, 2)))
            rows.append((pay_day, pay_desc[card][1], round(-total, 2)))

    # --- write files in each institution's layout ---
    checking.sort(key=lambda r: r[0])
    bal = 8000.0
    running = []
    for d, desc, amt in checking:
        bal += amt
        running.append((d, desc, amt, round(bal, 2)))
    _bofa_checking(raw / "BofA Checking" / "stmt_2022-2024.csv", [r for r in running if r[0] <= date(2024, 6, 30)], 8000.0)
    after = [r for r in running if r[0] >= date(2024, 1, 1)]  # overlaps Jan-Jun 2024 on purpose
    start_bal = next(r[3] - r[2] for r in after)
    _bofa_checking(raw / "BofA Checking" / "stmt_2024-2026.csv", after, start_bal)
    _write(raw / "BofA Customized Cash" / "card.csv", ["Posted Date", "Reference Number", "Payee", "Address", "Amount"],
           [[f"{d:%m/%d/%Y}", str(rnd.randint(10**22, 10**23)), desc, "NEW YORK NY", f"{a:.2f}"] for d, desc, a in sorted(cards["bofa"])])
    _write(raw / "Chase Sapphire" / "Chase1234_Activity.csv",
           ["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"],
           [[f"{d:%m/%d/%Y}", f"{d + timedelta(days=1):%m/%d/%Y}", desc, "", "Payment" if a > 0 else "Sale", f"{a:.2f}", ""]
            for d, desc, a in sorted(cards["chase"], reverse=True)])
    _write(raw / "Amex Gold" / "activity.csv", ["Date", "Description", "Card Member", "Account #", "Amount"],
           [[f"{d:%m/%d/%Y}", desc, "ALEX DOE", "-41009", f"{-a:.2f}"] for d, desc, a in sorted(cards["amex"], reverse=True)])
    _write(raw / "Robinhood" / "robinhood_activity.csv",
           ["Activity Date", "Process Date", "Settle Date", "Instrument", "Description", "Trans Code", "Quantity", "Price", "Amount"],
           [[f"{d.month}/{d.day}/{d.year}", f"{d.month}/{d.day}/{d.year}", f"{d.month}/{d.day}/{d.year}", inst, desc, code,
             str(q), f"${p:,.2f}" if p != "" else "", f"(${-a:,.2f})" if a < 0 else f"${a:,.2f}"]
            for code, d, inst, desc, q, p, a in sorted(robinhood, key=lambda r: r[1], reverse=True)]
           + [[""] * 9, ["", "", "", "", "", "", "", "", "The data provided is for informational purposes only."]])
    cb_rows = [[f"{rnd.getrandbits(48):012x}", f"{d:%Y-%m-%d} 15:04:05 UTC", typ, asset, f"{q}", "USD", f"${px:,.2f}",
                f"${sub:,.2f}", f"${tot:,.2f}", f"${fee:,.2f}", notes] for d, typ, asset, q, px, sub, tot, fee, notes in sorted(coinbase, key=lambda r: r[0])]
    _write(raw / "Coinbase" / "coinbase_history.csv",
           ["ID", "Timestamp", "Transaction Type", "Asset", "Quantity Transacted", "Price Currency", "Price at Transaction",
            "Subtotal", "Total (inclusive of fees and/or spread)", "Fees and/or Spread", "Notes"], cb_rows,
           preamble=[["Transactions"], ["User", "Alex Doe", "a1b2c3"]])

    # Wallet: cached Zerion responses, as `sync-wallets` would have saved them.
    (out / "wallets.csv").write_text(f"address,label\n{WALLET},Main\n")
    cache = out / "cache" / "zerion"
    cache.mkdir(parents=True)
    cb_hot = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"
    items = [
        _zerion_tx("2024-03-20T16:00:00Z", "receive", [("in", 1.5, "ETH", 4500.0, cb_hot, WALLET)], None),
        _zerion_tx("2024-06-02T12:00:00Z", "trade", [("out", 0.5, "ETH", 1900.0, WALLET, "0xpool"), ("in", 1895.0, "USDC", 1895.0, "0xpool", WALLET)], 6.4),
        _zerion_tx("2025-01-15T12:00:00Z", "claim", [("in", 120.0, "ZRO", 410.0, "0xdistributor", WALLET)], 2.1),
        _zerion_tx("2025-08-09T12:00:00Z", "send", [("out", 250.0, "USDC", 250.0, WALLET, "0x2222222222222222222222222222222222222222")], 0.3),
    ]
    (cache / f"{WALLET}.transactions.json").write_text(json.dumps(items))
    points, d, value = [], date(2024, 3, 20), 4500.0
    while d <= END:
        points.append([int((d - date(1970, 1, 1)).total_seconds()), round(value, 2)])
        value *= 1 + rnd.uniform(-0.12, 0.15)
        d += timedelta(days=30)
    (cache / f"{WALLET}.chart.json").write_text(json.dumps({"data": {"attributes": {"points": points}}}))

    _write(out / "w2.csv", ["year", "employer", "gross_pay", "taxes_withheld", "pretax_deductions"],
           [[y, "Acme Labs", g + (g * 0.1 if y >= 2024 else 0), round(g * 0.27), round(min(g * 0.08, 23000))] for y, g in GROSS.items() if y < 2026])
    rh_total, cb_total, bals = 0.0, 0.0, []
    for y in range(2022, 2026):
        rh_total = (rh_total + 12 * (500 + 250 * (y - 2022))) * 1.09
        cb_total = (cb_total + 4 * (1000 if y < 2025 else 1500)) * rnd.uniform(0.7, 1.6)
        bals += [[f"{y}-12-31", "Robinhood", round(rh_total)], [f"{y}-12-31", "Coinbase", round(cb_total)]]
    _write(out / "balances.csv", ["date", "account", "balance"], bals)
    (out / "rules.csv").write_text("pattern,category,merchant,direction,account\n"
                                   "WIRE TYPE:INTL IN.*GIFT,Bonus & Other Income,Gift from family,in,\n")
    for name in ("overrides.csv", "manual.csv"):
        (out / name).write_text("")


def _bofa_checking(path: Path, rows, start_balance: float) -> None:
    first, last = rows[0][0], rows[-1][0]
    credits = sum(a for _, _, a, _ in rows if a > 0)
    debits = sum(a for _, _, a, _ in rows if a < 0)
    body = [["Description", "", "Summary Amt."],
            [f"Beginning balance as of {first:%m/%d/%Y}", "", f"{start_balance:,.2f}"],
            ["Total credits", "", f"{credits:,.2f}"], ["Total debits", "", f"{debits:,.2f}"],
            [f"Ending balance as of {last:%m/%d/%Y}", "", f"{rows[-1][3]:,.2f}"], [],
            ["Date", "Description", "Amount", "Running Bal."],
            [f"{first:%m/%d/%Y}", f"Beginning balance as of {first:%m/%d/%Y}", "", f"{start_balance:,.2f}"]]
    body += [[f"{d:%m/%d/%Y}", desc, f"{a:,.2f}", f"{b:,.2f}"] for d, desc, a, b in rows]
    _write(path, None, body)


def _write(path: Path, header, rows, preamble=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for r in preamble:
            w.writerow(r)
        if header:
            w.writerow(header)
        w.writerows(rows)


def _zerion_tx(mined_at, op, legs, fee_usd):
    transfers = [{"direction": d, "quantity": {"float": q}, "value": v, "fungible_info": {"symbol": sym},
                  "sender": s, "recipient": r} for d, q, sym, v, s, r in legs]
    attrs = {"operation_type": op, "mined_at": mined_at, "status": "confirmed", "transfers": transfers,
             "sent_from": WALLET if op != "receive" else legs[0][4], "hash": "0x" + "ab" * 32,
             "flags": {"is_trash": False}}
    if fee_usd:
        attrs["fee"] = {"value": fee_usd}
    return {"type": "transactions", "attributes": attrs, "relationships": {"chain": {"data": {"id": "ethereum"}}}}
