"""Generate a next-session trading ticket from the latest paper run.

Usage:
  python -m quant_proto.tools.daily_orders <run_dir>

Prints a concise text summary and writes `orders_latest_day.csv` in the run dir.
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m quant_proto.tools.daily_orders <run_dir>", file=sys.stderr)
        return 2

    run_dir = sys.argv[1]
    orders_path = os.path.join(run_dir, "orders.csv")
    if not os.path.exists(orders_path):
        print(f"orders.csv not found: {orders_path}", file=sys.stderr)
        return 1

    rows = []
    with open(orders_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        print("No orders.")
        return 0

    # Find latest day present in orders
    days = sorted({r["day"] for r in rows})
    last_day = days[-1]
    last_rows = [r for r in rows if r["day"] == last_day]

    out_path = os.path.join(run_dir, "orders_latest_day.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["day", "symbol", "side", "qty", "reason"])
        w.writeheader()
        for r in last_rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    by_side = defaultdict(list)
    for r in last_rows:
        by_side[r["side"]].append(r)

    def fmt(rs):
        return ", ".join([f"{x['symbol']} {x['side']} {x['qty']}" for x in rs])

    print(f"Latest order day: {last_day}")
    if by_side.get("SELL"):
        print("SELL:", fmt(by_side["SELL"]))
    if by_side.get("BUY"):
        print("BUY:", fmt(by_side["BUY"]))
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
