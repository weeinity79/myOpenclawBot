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


Report with benchmark (default SPY):

```bash
python -m quant_proto report --run-dir runs/YYYY-MM-DD-HHMMSS --benchmark SPY
```

The report prints three sections:
- `Strategy`
- `Benchmark(SPY)`
- `Delta(Strategy-Benchmark)`

## Metrics definition (T1.3)

Annualization convention: **252 trading days**, and **rf=0** for Sharpe.

Given daily NAV series `NAV_t` and daily return `r_t = NAV_t / NAV_{t-1} - 1`:

- **Total Return** = `NAV_end / NAV_start - 1`
- **CAGR** = `(NAV_end / NAV_start)^(252/N) - 1` where `N` is number of trading days
- **Volatility(ann)** = `std(r_t) * sqrt(252)`
- **Sharpe(rf=0)** = `mean(r_t) / std(r_t) * sqrt(252)`
- **Max Drawdown** = `max(1 - NAV_t / cummax(NAV_t))`
- **Win Rate** = proportion of days where `r_t > 0`
- **Turnover** = average daily `(daily traded notional / NAV_t)`

Short sample policy: when sample length is `<20` trading days, `Volatility(ann)` and `Sharpe(rf=0)` degrade to `0.0` to avoid unstable estimates.


Execution constraints (T1.4, backward-compatible defaults):

```bash
python -m quant_proto backtest \
  --start 2022-01-01 --end 2022-12-31 \
  --min-trade-notional 0 \
  --lot-size 1 \
  --max-daily-turnover 1.0 \
  --gap-block-threshold 1.0
```

- `min_trade_notional`: minimum per-order notional to allow an order (default `0`, disabled)
- `lot_size`: order/fill share lot granularity (default `1`)
- `max_daily_turnover`: cap on `today BUY notional / prev-day NAV` in `[0,1]` (default `1.0`)
- `gap_block_threshold`: if `abs(next_open/close - 1)` is greater than threshold, block new BUY open (default `1.0`)

`orders.csv`/`fills.csv` reasons include:
- `rebalance`
- `below_min_notional`
- `rounded_lot`
- `blocked_turnover`
- `blocked_gap`

## Parameter sweep (T1.5)

Train/OOS 参数稳健性扫描：

```bash
python -m quant_proto.tools.param_sweep \
  --train-start 2020-01-01 --train-end 2022-12-30 \
  --oos-start 2023-01-03 --oos-end 2024-12-31 \
  --ma-fast-grid 10,20,30 \
  --ma-slow-grid 80,100,120 \
  --top-k-grid 2,3,4
```

输出目录默认：`runs/sweeps/YYYY-MM-DD-HHMMSS/`

- `sweep_results.csv`
  - 参数列：`ma_fast`,`ma_slow`,`top_k`
  - train 指标：`train_cagr`,`train_sharpe`,`train_maxdd`,`train_n_fills`
  - oos 指标：`oos_cagr`,`oos_sharpe`,`oos_maxdd`,`oos_n_fills`
  - 排名/稳健性：`rank_train`,`rank_oos`,`stability_score`
- `sweep_summary.json`
  - 网格、区间、推荐参数、OOS 门槛结果

参数校验：
- `ma_fast < ma_slow`
- `1 <= top_k <= universe_size`
- `oos_start > train_end`（不允许 train/oos 重叠）

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
