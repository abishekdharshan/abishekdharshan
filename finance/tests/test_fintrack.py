import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from fintrack import categorize as cat
from fintrack import ledger, report
from fintrack.importers import import_file
from fintrack.importers.common import parse_date, parse_money
from fintrack.importers.zerion import parse_wallet
from fintrack.model import Txn, assign_ids


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"))
    return path


def by_desc(txns):
    return {t.description: t for t in txns}


class Parsing(unittest.TestCase):
    def test_money(self):
        self.assertEqual(parse_money("$1,234.56"), 1234.56)
        self.assertEqual(parse_money("($1,234.56)"), -1234.56)
        self.assertEqual(parse_money("-45.10"), -45.10)
        self.assertEqual(parse_money("- $25.00"), -25.0)
        self.assertIsNone(parse_money(""))
        self.assertIsNone(parse_money("n/a"))

    def test_date(self):
        self.assertEqual(parse_date("01/05/2024"), "2024-01-05")
        self.assertEqual(parse_date("1/5/2024"), "2024-01-05")
        self.assertEqual(parse_date("2024-01-05 15:04:05 UTC"), "2024-01-05")
        self.assertEqual(parse_date("2024-01-05T15:04:05Z"), "2024-01-05")
        self.assertIsNone(parse_date("Total"))


class Importers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def imp(self, account, text, opts=None):
        return import_file(write(self.tmp / account / "x.csv", text), account, opts or {})

    def test_bofa_checking(self):
        fmt, txns, bals = self.imp("BofA Checking", '''
Description,,Summary Amt.
Beginning balance as of 01/01/2024,,"1,000.00"
Ending balance as of 01/31/2024,,"3,400.00"

Date,Description,Amount,Running Bal.
01/01/2024,Beginning balance as of 01/01/2024,,"1,000.00"
01/02/2024,"GUSTO DES:PAY 240102 ID:XX INDN:DOE,ALEX PPD","2,500.00","3,500.00"
01/03/2024,"CHECKCARD 0102 STARBUCKS STORE 123 NEW YORK NY","-100.00","3,400.00"
''')
        self.assertEqual(fmt, "bofa_checking")
        self.assertEqual([t.amount for t in txns], [2500.0, -100.0])
        self.assertEqual(txns[0].account_type, "checking")
        self.assertEqual([(b.date, b.balance) for b in bals], [("2024-01-01", 1000.0), ("2024-01-02", 3500.0), ("2024-01-03", 3400.0)])

    def test_card_sign_conventions(self):
        # Every card below has one $50 purchase and one $20 refund, in that bank's own convention.
        cases = {
            "BofA Card": ("bofa_credit", "Posted Date,Reference Number,Payee,Address,Amount\n"
                          "01/02/2024,123,SHOP,NY,-50.00\n01/03/2024,124,SHOP REFUND,NY,20.00\n"),
            "Chase Sapphire": ("chase_credit", "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
                               "01/02/2024,01/03/2024,SHOP,Shopping,Sale,-50.00,\n01/03/2024,01/04/2024,SHOP REFUND,Shopping,Return,20.00,\n"),
            "Amex Gold": ("amex", "Date,Description,Card Member,Account #,Amount\n"
                          "01/02/2024,SHOP,ALEX,-1003,50.00\n01/03/2024,SHOP REFUND,ALEX,-1003,-20.00\n"),
            "Apple Card": ("apple_card", "Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By\n"
                           "01/02/2024,01/03/2024,SHOP,Shop,Shopping,Purchase,50.00,Alex\n01/03/2024,01/04/2024,SHOP REFUND,Shop,Shopping,Return,-20.00,Alex\n"),
            "Citi Double Cash": ("citi", "Status,Date,Description,Debit,Credit\n"
                                 "Cleared,01/02/2024,SHOP,50.00,\nCleared,01/03/2024,SHOP REFUND,,-20.00\n"),
            "Capital One Venture": ("capital_one", "Transaction Date,Posted Date,Card No.,Description,Category,Debit,Credit\n"
                                    "2024-01-02,2024-01-03,1234,SHOP,Merchandise,50.00,\n2024-01-03,2024-01-04,1234,SHOP REFUND,Merchandise,,20.00\n"),
            "Discover It": ("discover", "Trans. Date,Post Date,Description,Amount,Category\n"
                            "01/02/2024,01/03/2024,SHOP,50.00,Merchandise\n01/03/2024,01/04/2024,SHOP REFUND,-20.00,Merchandise\n"),
            "US Bank Card 4444": ("us_bank", "Date,Transaction,Name,Memo,Amount\n"
                                  "2024-01-02,DEBIT,SHOP,x,-50.00\n2024-01-03,CREDIT,SHOP REFUND,x,20.00\n"),
        }
        for account, (want_fmt, text) in cases.items():
            with self.subTest(account):
                fmt, txns, _ = self.imp(account, text)
                self.assertEqual(fmt, want_fmt)
                self.assertEqual({t.description: t.amount for t in txns}, {"SHOP": -50.0, "SHOP REFUND": 20.0})
                self.assertEqual(txns[0].account_type, "credit")

    def test_generic_with_unsigned_amount_and_type_column(self):
        fmt, txns, _ = self.imp("Capital One 360 Checking", '''
Account Number,Transaction Description,Transaction Date,Transaction Type,Transaction Amount,Balance
1234,Deposit from ACME,01/02/24,Credit,1000.00,1500.00
1234,Debit Card Purchase - GROCER,01/03/24,Debit,45.20,1454.80
''')
        self.assertEqual(fmt, "generic")
        self.assertEqual({t.description: t.amount for t in txns}, {"Deposit from ACME": 1000.0, "Debit Card Purchase - GROCER": -45.2})
        self.assertEqual(txns[0].account_type, "checking")

    def test_generic_flips_positive_purchases(self):
        fmt, txns, _ = self.imp("Coinbase One Card", '''
Date,Merchant,Amount
2026-01-02,COFFEE,4.50
2026-01-03,BOOKS,20.00
2026-01-04,PAYMENT,-24.50
''')
        self.assertEqual(fmt, "generic")
        self.assertEqual([t.amount for t in txns], [-4.5, -20.0, 24.5])

    def test_account_ini_sign_override(self):
        write(self.tmp / "Odd Bank" / "_account.ini", "[account]\nsign = flip\ntype = savings\n")
        from fintrack.importers import read_account_options
        opts = read_account_options(self.tmp / "Odd Bank")
        _, txns, _ = self.imp("Odd Bank", "Date,Description,Amount\n01/02/2024,X,-5\n01/03/2024,Y,-6\n", opts)
        self.assertEqual([t.amount for t in txns], [5.0, 6.0])
        self.assertEqual(txns[0].account_type, "savings")

    def test_wells_fargo_headerless(self):
        fmt, txns, _ = self.imp("Wells Fargo Checking 5555",
                                '"01/02/2024","-12.50","*","","PURCHASE AUTHORIZED ON 01/01 SHAKE SHACK"\n'
                                '"01/03/2024","2000.00","*","","ACME PAYROLL"\n')
        self.assertEqual(fmt, "wells_fargo")
        self.assertEqual([t.amount for t in txns], [-12.5, 2000.0])

    def test_robinhood(self):
        fmt, txns, _ = self.imp("Robinhood", '''
"Activity Date","Process Date","Settle Date","Instrument","Description","Trans Code","Quantity","Price","Amount"
"1/2/2024","1/2/2024","1/3/2024","VTI","Vanguard Total Stock Market ETF
CUSIP: 922908769","Buy","2","$200.00","($400.00)"
"1/2/2024","1/2/2024","1/2/2024","","ACH Deposit","ACH","","","$400.00"
"1/15/2024","1/15/2024","1/15/2024","","ACH Deposit ACME INC PAYROLL","ACH","","","$5,000.00"
"1/20/2024","1/20/2024","1/20/2024","VTI","Cash Div: R/D 2024-01-18","CDIV","","","$3.10"
"1/21/2024","1/21/2024","1/21/2024","","Gold Subscription Fee","GOLD","","","($5.00)"
"","","","","","","","",""
"","","","","","","","","","The data provided is for informational purposes only."
''')
        self.assertEqual(fmt, "robinhood")
        cats = {t.description.split(" [")[0]: t.category for t in txns}
        self.assertEqual(cats["VTI Vanguard Total Stock Market ETF CUSIP: 922908769"], "Investment Trade")
        self.assertEqual(cats["ACH Deposit"], "Investment Transfer")
        self.assertEqual(cats["ACH Deposit ACME INC PAYROLL"], "")  # left for rules: not a plain deposit
        self.assertEqual(cats["VTI Cash Div: R/D 2024-01-18"], "Interest & Dividends")
        self.assertEqual(cats["Gold Subscription Fee"], "Subscriptions")
        payroll = next(t for t in txns if "PAYROLL" in t.description)
        cat.categorize([payroll], [], cat.load_rules(cat.DEFAULT_RULES)[0], {})
        self.assertEqual(payroll.category, "Salary")

    def test_coinbase(self):
        fmt, txns, _ = self.imp("Coinbase", '''
Transactions
User,Alex,abc
ID,Timestamp,Transaction Type,Asset,Quantity Transacted,Price Currency,Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),Fees and/or Spread,Notes
1,2024-01-02 15:04:05 UTC,Deposit,USD,1000,USD,$1.00,"$1,000.00","$1,000.00",$0.00,
2,2024-01-03 15:04:05 UTC,Buy,BTC,0.01,USD,"$40,000.00",$400.00,$405.00,$5.00,Bought
3,2024-01-04 15:04:05 UTC,Staking Income,ETH,0.001,USD,"$2,000.00",$2.00,$2.00,$0.00,
4,2024-01-05 15:04:05 UTC,Send,ETH,-0.5,USD,"$2,000.00","$1,000.00","$1,000.00",$0.00,to wallet
''')
        self.assertEqual(fmt, "coinbase")
        got = [(t.category, t.amount) for t in txns]
        self.assertEqual(got, [("Investment Transfer", 1000.0), ("Investment Trade", -405.0),
                               ("Crypto Rewards", 2.0), ("Crypto Transfer", -1000.0)])

    def test_schwab_brokerage(self):
        fmt, txns, _ = self.imp("Schwab Brokerage 666", '''
"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"
"01/02/2024 as of 12/29/2023","Qualified Dividend","SCHB","SCHWAB US BROAD MARKET ETF","","","","$12.34"
"01/03/2024","Buy","SCHB","SCHWAB US BROAD MARKET ETF","10","$55.00","","-$550.00"
"01/04/2024","MoneyLink Transfer","","Tfr BANK OF AMERICA, ALEX","","","","$1,000.00"
''')
        self.assertEqual(fmt, "schwab")
        self.assertEqual([(t.date, t.category, t.amount) for t in txns], [
            ("2024-01-02", "Interest & Dividends", 12.34), ("2024-01-03", "Investment Trade", -550.0),
            ("2024-01-04", "Investment Transfer", 1000.0)])

    def test_unrecognized(self):
        fmt, txns, _ = self.imp("Mystery", "foo,bar\n1,2\n")
        self.assertIsNone(fmt)


class Categorize(unittest.TestCase):
    def defaults(self):
        return cat.load_rules(cat.DEFAULT_RULES)[0]

    def t(self, desc, amount, account="BofA Checking", typ="checking", **kw):
        return Txn(date=kw.pop("date", "2024-01-02"), account=account, description=desc, amount=amount, source="test",
                   account_type=typ, **kw)

    def test_default_rules(self):
        cases = [
            ("GUSTO DES:PAY 240102 ID:XX INDN:DOE PPD", 2500, "Salary"),
            ("JUSTWORKS PAYROLL DES:PAYROLL", 2500, "Salary"),
            ("Online Banking payment to CRD 4521 Confirmation# 123", -900, "Credit Card Payment"),
            ("CHASE CREDIT CRD DES:AUTOPAY", -900, "Credit Card Payment"),
            ("AMEX EPAYMENT DES:ACH PMT", -900, "Credit Card Payment"),
            ("CITI CARD ONLINE DES:PAYMENT", -900, "Credit Card Payment"),
            ("ROBINHOOD DES:FUNDS", -500, "Investment Transfer"),
            ("COINBASE INC. DES:8889087930", -500, "Investment Transfer"),
            ("Zelle payment to SAM for dinner", -40, "P2P Payments"),
            ("VENMO DES:PAYMENT", -40, "P2P Payments"),
            ("Online Banking transfer to SAV 1234", -1000, "Transfer"),
            ("REVOLUT DES:TOPUP", -300, "Transfer"),
            ("BILT DES:RENT PAYMT", -3000, "Rent & Housing"),
            ("UBER EATS", -30, "Dining & Drinks"),
            ("UBER *TRIP HELP.UBER.COM", -20, "Transport"),
            ("AMAZON PRIME*AB1CD", -15, "Subscriptions"),
            ("AMZN Mktp US*2K3LJ4", -45, "Shopping"),
            ("WHOLEFDS MKT 10234", -80, "Groceries"),
            ("DELTA AIR 0062341234567", -400, "Travel"),
            ("IRS TREAS 310 DES:TAX REF", 1200, "Taxes"),
        ]
        rules = self.defaults()
        for desc, amount, want in cases:
            with self.subTest(desc):
                txn = self.t(desc, amount)
                cat.categorize([txn], [], rules, {})
                self.assertEqual(txn.category, want)

    def test_card_side_payment_needs_credit_account(self):
        on_card = self.t("PAYMENT - THANK YOU", 900, account="Chase Sapphire 2222", typ="credit")
        on_checking = self.t("ONLINE PAYMENT FROM ACME", 900)
        cat.categorize([on_card, on_checking], [], self.defaults(), {})
        self.assertEqual(on_card.category, "Credit Card Payment")
        self.assertEqual(on_checking.category, "Uncategorized Income")

    def test_precedence(self):
        rules = self.defaults()
        user = [cat.Rule(__import__("re").compile("ACH DEPOSIT", 2), "Salary")]
        preset = self.t("ACH Deposit", 100, account="Robinhood", typ="brokerage", category="Investment Transfer")
        cat.categorize([preset], user, rules, {})
        self.assertEqual(preset.category, "Salary")  # user rule beats importer preset
        txn = self.t("WHOLEFDS MKT", -80)
        assign_ids([txn])
        cat.categorize([txn], [], rules, {txn.id: {"category": "Gifts & Donations", "merchant": "Gift basket"}})
        self.assertEqual((txn.category, txn.merchant), ("Gifts & Donations", "Gift basket"))

    def test_transfer_matching(self):
        out = self.t("SOME BANK WEIRD DEBIT 1234", -750.0, date="2024-03-01")
        into = self.t("INCOMING 9876", 750.0, account="Juno", date="2024-03-03")
        refund_same_acct = self.t("MYSTERY CREDIT", 750.0, date="2024-03-02")
        cat.categorize([out, into, refund_same_acct], [], [], {})
        self.assertEqual((out.category, into.category), ("Transfer", "Transfer"))
        self.assertEqual(refund_same_acct.category, "Uncategorized Income")

    def test_uncategorized_card_credit_is_a_refund(self):
        credit = self.t("MERCHANT CREDIT", 25, account="Amex 33333", typ="credit")
        cat.categorize([credit], [], [], {})
        self.assertEqual(credit.category, "Refunds & Credits")

    def test_clean_merchant(self):
        self.assertEqual(cat.clean_merchant("CHECKCARD 0102 BLUE BOTTLE COFFEE 12345 NEW YORK NY 24431064"), "Blue Bottle Coffee")
        self.assertEqual(cat.clean_merchant("TST* JOE'S PIZZA NEW YORK NY"), "Joe's Pizza")
        self.assertEqual(cat.clean_merchant("AMZN Mktp US*2K3LJ4 Amzn.com/bill WA"), "Amazon")
        self.assertEqual(cat.clean_merchant("ACME CORP DES:PAYROLL ID:123 INDN:DOE PPD"), "Acme Corp")


class Wallets(unittest.TestCase):
    ME, OTHER_OWN = "0xaaa", "0xbbb"

    def tx(self, op, transfers, sent_from, fee=None):
        a = {"operation_type": op, "mined_at": "2025-01-02T00:00:00Z", "transfers": transfers, "sent_from": sent_from}
        if fee:
            a["fee"] = {"value": fee}
        return {"attributes": a, "relationships": {"chain": {"data": {"id": "base"}}}}

    def test_parse(self):
        items = [
            self.tx("receive", [{"direction": "in", "quantity": {"float": 1}, "value": 3000, "fungible_info": {"symbol": "ETH"},
                                 "sender": "0xCoinbase", "recipient": self.ME}], "0xcoinbase"),
            self.tx("trade", [{"direction": "out", "quantity": {"float": 1}, "value": 3000, "fungible_info": {"symbol": "ETH"}},
                              {"direction": "in", "quantity": {"float": 2990}, "value": 2990, "fungible_info": {"symbol": "USDC"}}],
                    self.ME, fee=1.5),
            self.tx("claim", [{"direction": "in", "quantity": {"float": 10}, "value": 40, "fungible_info": {"symbol": "OP"}}], self.ME),
            self.tx("receive", [{"direction": "in", "quantity": {"float": 5}, "value": None, "fungible_info": {"symbol": "SPAM"},
                                 "sender": "0xspam"}], "0xspam"),
        ]
        txns = parse_wallet(self.ME, "Main", items, {self.ME, self.OTHER_OWN})
        got = [(t.category, t.amount) for t in txns]
        self.assertEqual(got, [("Crypto Transfer", 3000.0), ("Investment Trade", -10.0), ("Fees & Interest", -1.5),
                               ("Crypto Rewards", 40.0)])
        self.assertIn("from 0xcoinbase", txns[0].description)  # rules can key on the counterparty


class EndToEnd(unittest.TestCase):
    def test_overlapping_exports_are_deduplicated(self):
        d = Path(tempfile.mkdtemp())
        head = "Date,Description,Amount,Running Bal.\n"
        write(d / "raw" / "BofA Checking" / "a.csv", head + "01/02/2024,COFFEE,-5.00,95.00\n01/02/2024,COFFEE,-5.00,90.00\n"
                                                          "01/03/2024,GUSTO DES:PAY,1000.00,1090.00\n")
        write(d / "raw" / "BofA Checking" / "b.csv", head + "01/02/2024,COFFEE,-5.00,95.00\n01/02/2024,COFFEE,-5.00,90.00\n"
                                                          "01/03/2024,GUSTO DES:PAY,1000.00,1090.00\n01/04/2024,TRADER JOE S,-40.00,1050.00\n")
        ds = ledger.load(d)
        self.assertEqual(sorted(t.amount for t in ds.txns), [-40.0, -5.0, -5.0, 1000.0])  # both coffees kept, nothing doubled

    def test_demo_books_balance(self):
        from fintrack.demo import generate
        d = Path(tempfile.mkdtemp()) / "demo"
        generate(d)
        ds = ledger.load(d)
        net = {}
        for t in ds.txns:
            net[t.category] = net.get(t.category, 0) + t.amount
        # Every card payment and brokerage deposit has both sides in the data, so they cancel out.
        self.assertAlmostEqual(net["Credit Card Payment"], 0, places=2)
        self.assertAlmostEqual(net["Investment Transfer"], 0, places=2)
        years = {r["year"]: r for r in report.yearly(ds)}
        self.assertGreater(years["2025"]["earned"], years["2022"]["earned"])
        data = report.report_data(ds, "test")
        self.assertEqual(len(data["txns"]), len(ds.txns))
        self.assertIsNotNone(data["networth"])
        out = d / "report.html"
        report.write_html(data, out)
        self.assertNotIn("/*__DATA__*/null", out.read_text())


if __name__ == "__main__":
    unittest.main()
