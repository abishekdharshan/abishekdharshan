from __future__ import annotations

import csv
import re
from datetime import datetime
from typing import Iterator, Optional


def read_rows(path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        return [row for row in csv.reader(f)]


def lower_cells(row: list[str]) -> list[str]:
    return [c.strip().lower() for c in row]


def find_header(rows: list[list[str]], required: set[str], scan: int = 40) -> Optional[int]:
    """Index of the first row whose cells include every name in `required`."""
    for i, row in enumerate(rows[:scan]):
        cells = set(lower_cells(row))
        if required <= cells:
            return i
    return None


def records(rows: list[list[str]], header_idx: int) -> Iterator[dict[str, str]]:
    header = lower_cells(rows[header_idx])
    for row in rows[header_idx + 1 :]:
        if not any(c.strip() for c in row):
            continue
        yield {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header) if h}


def parse_money(s: Optional[str]) -> Optional[float]:
    """'$1,234.56' / '(1,234.56)' / '-1234.56' / '1234.56-' -> float. Blank -> None."""
    s = (s or "").strip()
    if not s:
        return None
    neg = "(" in s or "-" in s
    digits = re.sub(r"[^\d.]", "", s)
    if not digits or digits == "." or digits.count(".") > 1:
        return None
    v = float(digits)
    return -v if neg else v


_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y", "%d %b %Y", "%b %d, %Y", "%Y/%m/%d")


def parse_date(s: Optional[str]) -> Optional[str]:
    """Most bank date spellings -> 'YYYY-MM-DD'. Unparseable -> None."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]", s)
    if m:
        s = m.group(1)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None
