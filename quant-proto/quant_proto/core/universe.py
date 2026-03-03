from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from quant_proto.utils.dates import fmt_yyyy_mm_dd
from quant_proto.utils.io import sha256_text, write_json


DEFAULT_UNIVERSE: list[str] = [
    "SPY",
    "QQQ",
    "IWM",
    "TLT",
    "GLD",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
]


@dataclass(frozen=True)
class UniverseSnapshot:
    asof: date
    symbols: tuple[str, ...]
    version_hash: str


def snapshot_universe(asof: date, symbols: Sequence[str]) -> UniverseSnapshot:
    cleaned = tuple(sorted({s.upper().strip() for s in symbols if s and s.strip()}))
    version_hash = sha256_text("\n".join(cleaned))
    return UniverseSnapshot(asof=asof, symbols=cleaned, version_hash=version_hash)


def write_universe_snapshot(run_dir: Path, snap: UniverseSnapshot) -> Path:
    payload = {
        "asof": fmt_yyyy_mm_dd(snap.asof),
        "symbols": list(snap.symbols),
        "version_hash": snap.version_hash,
    }
    p = run_dir / "universe_snapshot.json"
    write_json(p, payload)
    return p
