"""Format detection: look at a CSV's header row and pick the matching importer."""

from __future__ import annotations

import configparser
from pathlib import Path

from . import banks, brokers
from .common import read_rows


def read_account_options(folder: Path) -> dict:
    """Optional <account folder>/_account.ini:

        [account]
        type = credit      ; checking | savings | credit | brokerage | crypto
        sign = auto        ; auto | as-is | flip  (only for files the generic importer reads)
    """
    ini = folder / "_account.ini"
    if not ini.exists():
        return {}
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cp.read(ini)
    return {k: v.strip().lower() for k, v in cp["account"].items()} if cp.has_section("account") else {}


def import_file(path: Path, account: str, opts: dict):
    """-> (format name, txns, balances); format name is None if unrecognized."""
    rows = read_rows(path)
    idx = brokers.detect_robinhood(rows)
    if idx is not None:
        return ("robinhood", *brokers.parse_robinhood(rows, idx, account, opts))
    idx = brokers.detect_coinbase(rows)
    if idx is not None:
        return ("coinbase", *brokers.parse_coinbase(rows, idx, account, opts))
    idx = brokers.detect_schwab(rows)
    if idx is not None:
        return ("schwab", *brokers.parse_schwab(rows, idx, account, opts))
    if banks.is_wells_fargo(rows):
        return ("wells_fargo", *banks.parse_wells_fargo(rows, account, opts))
    known = banks.detect_known(rows)
    if known:
        fmt, idx = known
        return (fmt.name, *banks.parse_known(rows, idx, fmt, account, opts))
    generic = banks.detect_generic(rows)
    if generic:
        idx, cols = generic
        return ("generic", *banks.parse_generic(rows, idx, cols, account, opts))
    return None, [], []
