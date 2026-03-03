from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from quant_proto.core.broker import Broker, BrokerConfig, Order
from quant_proto.core.indicators import atr
from quant_proto.core.strategy import TrendStrategyConfig, compute_signal_frame, target_weights_for_date
from quant_proto.core.universe import DEFAULT_UNIVERSE, UniverseSnapshot, snapshot_universe, write_universe_snapshot
from quant_proto.utils.dates import fmt_yyyy_mm_dd
from quant_proto.utils.io import ensure_dir, write_csv, write_json
from quant_proto.utils.stooq import ensure_data


@dataclass(frozen=True)
class RiskConfig:
    max_drawdown: float = 0.10
    per_trade_risk: float = 0.005
    position_cap: float = 0.20
    stop_atr_mult: float = 2.0
    cooldown_days: int = 10
    recovery_drawdown: float = 0.06
    ramp_steps: Tuple[Tuple[int, float], ...] = ((5, 0.25), (5, 0.50), (5, 1.00))


@dataclass(frozen=True)
class SimConfig:
    start: date
    end: date
    initial_cash: float = 100_000.0
    universe: Tuple[str, ...] = tuple(DEFAULT_UNIVERSE)
    data_dir: str = "data"
    strategy: TrendStrategyConfig = field(default_factory=TrendStrategyConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


@dataclass
class RiskState:
    mode: str = "NORMAL"  # NORMAL, OFF, RAMP
    cooldown_left: int = 0
    ramp_step_idx: int = 0
    ramp_step_left: int = 0
    exposure_factor: float = 1.0


def _make_run_dir(base: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    run_dir = base / ts
    ensure_dir(run_dir)
    return run_dir


def _align_market_data(data_by_symbol: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # inner join on Date to ensure all symbols have bars for each trading day
    merged: Optional[pd.DataFrame] = None
    for sym, df in data_by_symbol.items():
        t = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        t = t.rename(columns={
            "Open": f"{sym}_Open",
            "High": f"{sym}_High",
            "Low": f"{sym}_Low",
            "Close": f"{sym}_Close",
            "Volume": f"{sym}_Volume",
        })
        merged = t if merged is None else merged.merge(t, on="Date", how="inner")
    assert merged is not None
    merged = merged.sort_values("Date").reset_index(drop=True)
    return merged


def _calc_target_qty(
    symbol: str,
    weight: float,
    nav: float,
    close_px: float,
    stop_dist: float,
    risk_cfg: RiskConfig,
    exposure_factor: float,
) -> int:
    if close_px <= 0:
        return 0

    max_notional = nav * risk_cfg.position_cap * exposure_factor
    desired_notional = nav * float(weight) * exposure_factor
    desired_notional = min(desired_notional, max_notional)
    desired_qty = int(desired_notional // close_px)

    # Risk sizing (worst-case loss if stop hit)
    if stop_dist and stop_dist > 0:
        risk_budget = nav * risk_cfg.per_trade_risk
        risk_qty = int(risk_budget // stop_dist)
        desired_qty = min(desired_qty, risk_qty)
    else:
        desired_qty = 0

    return max(desired_qty, 0)


def _risk_update(state: RiskState, dd: float, risk_cfg: RiskConfig) -> None:
    if dd >= risk_cfg.max_drawdown:
        state.mode = "OFF"
        state.cooldown_left = risk_cfg.cooldown_days
        state.exposure_factor = 0.0
        return

    if state.mode == "OFF":
        if state.cooldown_left > 0:
            state.cooldown_left -= 1
            state.exposure_factor = 0.0
            return
        # cooldown complete; require recovery
        if dd <= risk_cfg.recovery_drawdown:
            # start ramp
            state.mode = "RAMP"
            state.ramp_step_idx = 0
            days, expo = risk_cfg.ramp_steps[0]
            state.ramp_step_left = days
            state.exposure_factor = expo
        else:
            state.exposure_factor = 0.0
        return

    if state.mode == "RAMP":
        if state.ramp_step_left > 0:
            state.ramp_step_left -= 1
        if state.ramp_step_left <= 0:
            state.ramp_step_idx += 1
            if state.ramp_step_idx >= len(risk_cfg.ramp_steps):
                state.mode = "NORMAL"
                state.exposure_factor = 1.0
            else:
                days, expo = risk_cfg.ramp_steps[state.ramp_step_idx]
                state.ramp_step_left = days
                state.exposure_factor = expo
        return

    # NORMAL
    state.exposure_factor = 1.0


def run_sim(
    cfg: SimConfig,
    mode: str,
    run_base_dir: Path,
    force_refresh_data: bool = False,
) -> Path:
    """Run a backtest/paper simulation.

    mode: 'backtest' or 'paper' (same engine; paper emphasizes artifacts).
    """
    run_dir = _make_run_dir(run_base_dir)

    # Universe snapshot as-of start date
    snap = snapshot_universe(cfg.start, cfg.universe)
    write_universe_snapshot(run_dir, snap)

    # Fetch/cache data
    data_dir = Path(cfg.data_dir)
    data_by_symbol: Dict[str, pd.DataFrame] = {}
    for sym in cfg.universe:
        data_by_symbol[sym] = ensure_data(data_dir, sym, force=force_refresh_data)

    # Precompute signals + ATR
    signals_by_symbol: Dict[str, pd.DataFrame] = {}
    atr_by_symbol: Dict[str, pd.Series] = {}
    for sym, df in data_by_symbol.items():
        s = compute_signal_frame(df, cfg.strategy)
        a = atr(df, window=14) * cfg.risk.stop_atr_mult
        s = s.merge(a.rename("stop_dist"), left_index=True, right_index=True)
        signals_by_symbol[sym] = s
        atr_by_symbol[sym] = a

    # Align calendar across all symbols
    market = _align_market_data({sym: data_by_symbol[sym] for sym in cfg.universe})

    market["d"] = market["Date"].dt.date
    market = market[(market["d"] >= cfg.start) & (market["d"] <= cfg.end)].reset_index(drop=True)
    if len(market) < 3:
        raise RuntimeError("Not enough market data in selected date range")

    broker = Broker(cfg.broker, init_cash=cfg.initial_cash)
    risk_state = RiskState()

    pending_orders: Dict[date, List[Order]] = {}
    orders_log: List[dict] = []
    fills_log: List[dict] = []
    equity_log: List[dict] = []

    peak_nav = cfg.initial_cash

    # Loop over trading days; orders execute at today's open, generated from prior close
    for idx in range(len(market)):
        row = market.iloc[idx]
        today: date = row["d"]

        # Settle cash
        broker.process_settlements(today)
        broker.reset_reserved()

        # Execute any orders at open
        open_prices = {sym: float(row[f"{sym}_Open"]) for sym in cfg.universe}
        todays_orders = pending_orders.pop(today, [])

        # We pass stop distances for buys based on *yesterday's* signal row.
        stop_dists_for_today: Dict[str, float] = {}
        if idx > 0:
            prev_ts = market.iloc[idx - 1]["Date"]
            for sym in cfg.universe:
                sdf = signals_by_symbol[sym]
                r = sdf.loc[sdf["Date"] == prev_ts]
                if not r.empty:
                    sd = r.iloc[0].get("stop_dist")
                    if pd.notna(sd):
                        stop_dists_for_today[sym] = float(sd)

        fills = broker.execute_orders(today, open_prices, todays_orders, stop_dist_by_symbol=stop_dists_for_today)
        for o in todays_orders:
            orders_log.append({
                "day": fmt_yyyy_mm_dd(o.day),
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "reason": o.reason,
            })
        for f in fills:
            fills_log.append({
                "day": fmt_yyyy_mm_dd(f.day),
                "symbol": f.symbol,
                "side": f.side,
                "qty": f.qty,
                "price": f.price,
                "notional": f.notional,
                "commission": f.commission,
                "slippage_bps": f.slippage_bps,
                "reason": f.reason,
            })

        # End-of-day valuation
        close_prices = {sym: float(row[f"{sym}_Close"]) for sym in cfg.universe}
        nav = broker.equity(close_prices)
        peak_nav = max(peak_nav, nav)
        dd = 0.0 if peak_nav <= 0 else (peak_nav - nav) / peak_nav

        _risk_update(risk_state, dd, cfg.risk)

        equity_log.append({
            "day": fmt_yyyy_mm_dd(today),
            "nav": nav,
            "peak": peak_nav,
            "drawdown": dd,
            "risk_mode": risk_state.mode,
            "exposure_factor": risk_state.exposure_factor,
            "settled_cash": broker.state.cash.settled,
            "reserved_cash": broker.state.cash.reserved,
            "available_cash": broker.state.cash.available,
            "pending_cash": sum(amt for _, amt in broker.state.cash.pending),
        })

        # Generate orders for next trading day (signal after close)
        if idx == len(market) - 1:
            break
        next_day: date = market.iloc[idx + 1]["d"]
        asof_ts = row["Date"]

        if risk_state.exposure_factor <= 0.0:
            tgt_w = {}
        else:
            tgt_w = target_weights_for_date(
                signals_by_symbol=signals_by_symbol,
                asof_ts=asof_ts,
                cfg=cfg.strategy,
                max_gross=1.0,
            )

        # Convert weights to target quantities (using today's close and stop_dist as-of today)
        target_qty: Dict[str, int] = {}
        stop_dist_today: Dict[str, float] = {}
        for sym in cfg.universe:
            sdf = signals_by_symbol[sym]
            r = sdf.loc[sdf["Date"] == asof_ts]
            if r.empty:
                continue
            sd = r.iloc[0].get("stop_dist")
            stop_dist_today[sym] = float(sd) if pd.notna(sd) else 0.0

        for sym, w in tgt_w.items():
            q = _calc_target_qty(
                symbol=sym,
                weight=w,
                nav=nav,
                close_px=close_prices[sym],
                stop_dist=stop_dist_today.get(sym, 0.0),
                risk_cfg=cfg.risk,
                exposure_factor=risk_state.exposure_factor,
            )
            target_qty[sym] = q

        # Build orders from current -> target
        orders_next: List[Order] = []
        for sym in cfg.universe:
            cur = broker.state.position_qty(sym)
            tgt = target_qty.get(sym, 0)
            if tgt < cur:
                orders_next.append(Order(day=next_day, symbol=sym, side="SELL", qty=cur - tgt, reason="rebalance"))
            elif tgt > cur:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=tgt - cur, reason="rebalance"))

        pending_orders[next_day] = orders_next

    # Write artifacts
    cfg_payload = {
        "mode": mode,
        "start": fmt_yyyy_mm_dd(cfg.start),
        "end": fmt_yyyy_mm_dd(cfg.end),
        "initial_cash": cfg.initial_cash,
        "universe": list(cfg.universe),
        "strategy": asdict(cfg.strategy),
        "broker": asdict(cfg.broker),
        "risk": {
            **asdict(cfg.risk),
            "ramp_steps": [list(x) for x in cfg.risk.ramp_steps],
        },
    }
    write_json(run_dir / "config.json", cfg_payload)

    write_csv(run_dir / "orders.csv", orders_log, ["day", "symbol", "side", "qty", "reason"])
    write_csv(
        run_dir / "fills.csv",
        fills_log,
        ["day", "symbol", "side", "qty", "price", "notional", "commission", "slippage_bps", "reason"],
    )
    write_csv(
        run_dir / "equity_curve.csv",
        equity_log,
        ["day", "nav", "peak", "drawdown", "risk_mode", "exposure_factor", "settled_cash", "reserved_cash", "available_cash", "pending_cash"],
    )

    return run_dir
