from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


def parse_yyyy_mm_dd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def fmt_yyyy_mm_dd(d: date) -> str:
    return d.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
