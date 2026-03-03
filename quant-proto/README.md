US ETF Daily Quant Prototype (v1)

This is a runnable **educational prototype** of a US ETF-only, long-only, cash-account daily quant system.

It is **not** trading advice and is **not** production-ready for live trading.

## Features (prototype scope)

- **Universe:** static allowlist of US ETFs (default: SPY, QQQ, IWM, TLT, GLD, XLF, XLK, XLE, XLV)
  - Writes a **daily universe snapshot** file with a version hash.
- **Free data ingestion:** daily OHLCV from **Stooq** (CSV), cached to `data/stooq/`.
- **Strategy:** simple trend-following
  - Signal computed after close: `SMA(20) > SMA(100)` on **Close**
  - Optional **top-K** selection (default K=3) by `ma_fast/ma_slow`
  - **Rebalance:** daily (signal after close, execute next open)
- **Execution model:** market-at-open next day with
  - `slippage_bps` (default 5 bps)
  - `commission_bps` (default 1 bp)
- **Cash account model:**
  - **T+1 settlement** simulated for sale proceeds
  - Buys are blocked/downsized if insufficient **settled cash**
- **Risk controls:**
  - Position cap: **20% of NAV**
  - Per-trade risk sizing: **0.5% NAV** using a v1 stop distance = `ATR14 * 2`
  - Max drawdown **10%** triggers **risk-off** (liquidate and block new opens)
    - cooldown: 10 trading days
    - recovery threshold: DD < 6% then staged ramp back in (25% -> 50% -> 100%)

## Setup

Create and activate a virtual environment:

```bash
cd /home/jie/.openclaw/workspace/quant-proto
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install pandas numpy
```

## Run

Backtest:

```bash
. .venv/bin/activate
python -m quant_proto backtest --start 2018-01-01 --end 2024-12-31
```

Paper sim (same engine; writes the same artifacts):

```bash
python -m quant_proto paper --start 2023-01-01 --end 2024-12-31
```

Report the latest run:

```bash
python -m quant_proto report
```

## Output artifacts

Each run writes to:

`runs/YYYY-MM-DD-HHMMSS/`

- `config.json`
- `universe_snapshot.json`
- `orders.csv` (target-generated orders, for next-open)
- `fills.csv` (executed fills with slippage & commission)
- `equity_curve.csv` (NAV, drawdown, risk mode, cash)

## Notes / Limitations

- This prototype uses Stooq daily bars; data quality/adjustment conventions can vary by instrument.
- No corporate actions handling.
- No borrow, no shorting, no leverage.
- Settlement modeling is simplified (T+1 uses next calendar day; the simulator settles on trading days).
- Risk sizing uses ATR-based stop distance but does not simulate stop execution intraday.

## License

Internal prototype / educational.
