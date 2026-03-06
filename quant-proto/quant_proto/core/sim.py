from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from quant_proto.core.broker import Broker, BrokerConfig, Order, bps
from quant_proto.core.data_quality import DataQualityConfig, validate_data
from quant_proto.core.indicators import atr
from quant_proto.core.strategy import TrendStrategyConfig, compute_signal_frame, target_weights_for_date
from quant_proto.core.universe import DEFAULT_UNIVERSE, snapshot_universe, write_universe_snapshot
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
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)


@dataclass
class RiskState:
    mode: str = "NORMAL"  # NORMAL, OFF, RAMP
    cooldown_left: int = 0
    ramp_step_idx: int = 0
    ramp_step_left: int = 0
    exposure_factor: float = 1.0


def _validate_exec_constraints(cfg: SimConfig) -> None:
    if cfg.broker.lot_size <= 0:
        raise ValueError(f"invalid broker.lot_size={cfg.broker.lot_size}; must be > 0")
    if cfg.broker.min_trade_notional < 0:
        raise ValueError(f"invalid broker.min_trade_notional={cfg.broker.min_trade_notional}; must be >= 0")
    if cfg.broker.max_daily_turnover < 0 or cfg.broker.max_daily_turnover > 1:
        raise ValueError(f"invalid broker.max_daily_turnover={cfg.broker.max_daily_turnover}; must be in [0,1]")
    if cfg.broker.gap_block_threshold < 0:
        raise ValueError(f"invalid broker.gap_block_threshold={cfg.broker.gap_block_threshold}; must be >= 0")


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
        t = t.rename(
            columns={
                "Open": f"{sym}_Open",
                "High": f"{sym}_High",
                "Low": f"{sym}_Low",
                "Close": f"{sym}_Close",
                "Volume": f"{sym}_Volume",
            }
        )
        merged = t if merged is None else merged.merge(t, on="Date", how="inner")
    assert merged is not None
    merged = merged.sort_values("Date").reset_index(drop=True)
    return merged


def _calc_target_qty(
    *,
    symbol: str,
    weight: float,
    nav: float,
    close_px: float,
    next_open_px: float,
    stop_dist: float,
    risk_cfg: RiskConfig,
    exposure_factor: float,
    slippage_bps_: float,
    commission_bps_: float,
    available_cash: float,
) -> tuple[int, dict]:
    """Return (target_qty, audit_dict) for a symbol."""

    if close_px <= 0:
        return 0, {"symbol": symbol, "error": "bad_close_px"}

    # Expected execution price for BUYs (orders generated after close, execute next open).
    exec_px = float(next_open_px) if next_open_px and next_open_px > 0 else float(close_px)
    if slippage_bps_ and slippage_bps_ > 0:
        exec_px = exec_px * (1.0 + bps(slippage_bps_))

    # Hard cap on position notional
    max_notional = nav * risk_cfg.position_cap * exposure_factor

    # Weight-based desired notional (still subject to cap and risk and cash)
    desired_notional = nav * float(weight) * exposure_factor
    desired_notional_capped = min(desired_notional, max_notional)

    # Convert desired notional to integer shares (use close for initial sizing, then cap using exec price)
    desired_qty_by_weight = int(desired_notional_capped // close_px)

    # Strict cap enforcement after rounding (no tolerance) using expected execution price
    max_cap_qty = int(max_notional // exec_px) if exec_px > 0 else 0

    # Per-trade risk sizing
    risk_budget = nav * risk_cfg.per_trade_risk
    shares_by_risk = int(risk_budget // stop_dist) if (stop_dist and stop_dist > 0) else 0

    # Cash sizing: only allow spending settled/available cash (no pending).
    # Mirror broker's affordability math.
    per_share_all_in = exec_px * (1.0 + bps(commission_bps_))
    shares_by_cash = int(available_cash // per_share_all_in) if per_share_all_in > 0 else 0

    final_qty = desired_qty_by_weight
    final_qty = min(final_qty, max_cap_qty)
    final_qty = min(final_qty, shares_by_risk)
    final_qty = min(final_qty, shares_by_cash)
    final_qty = max(int(final_qty), 0)

    audit = {
        "symbol": symbol,
        "weight": float(weight),
        "nav": float(nav),
        "exposure_factor": float(exposure_factor),
        "close_px": float(close_px),
        "next_open_px": float(next_open_px),
        "exec_px": float(exec_px),
        "slippage_bps": float(slippage_bps_),
        "commission_bps": float(commission_bps_),
        "available_cash": float(available_cash),
        "position_cap": float(risk_cfg.position_cap),
        "max_notional": float(max_notional),
        "desired_notional": float(desired_notional),
        "desired_notional_capped": float(desired_notional_capped),
        "desired_qty_by_weight": int(desired_qty_by_weight),
        "max_cap_qty": int(max_cap_qty),
        "per_trade_risk": float(risk_cfg.per_trade_risk),
        "risk_budget": float(risk_budget),
        "stop_dist": float(stop_dist),
        "shares_by_risk": int(shares_by_risk),
        "shares_by_cash": int(shares_by_cash),
        "final_target_qty": int(final_qty),
    }

    return final_qty, audit


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
    _validate_exec_constraints(cfg)
    run_dir = _make_run_dir(run_base_dir)

    # Universe snapshot as-of start date
    snap = snapshot_universe(cfg.start, cfg.universe)
    write_universe_snapshot(run_dir, snap)

    # Fetch/cache data
    data_dir = Path(cfg.data_dir)
    data_by_symbol: Dict[str, pd.DataFrame] = {}
    for sym in cfg.universe:
        data_by_symbol[sym] = ensure_data(data_dir, sym, force=force_refresh_data)

    # Data quality checks (fail-fast with structured report)
    dq = validate_data(data_by_symbol, start=cfg.start, end=cfg.end, cfg=cfg.data_quality)
    write_json(run_dir / "data_quality_report.json", {
        "passed": dq.passed,
        "config": dq.config,
        "total_symbols": dq.total_symbols,
        "warnings": dq.warnings,
        "errors": dq.errors,
    })
    if not dq.passed:
        first = dq.errors[0] if dq.errors else {"symbol": "NA", "day": "NA", "rule": "unknown"}
        raise ValueError(f"[DATA_ERROR] symbol={first['symbol']} day={first['day']} rule={first['rule']}")

    # Precompute signals + ATR stop distance
    signals_by_symbol: Dict[str, pd.DataFrame] = {}
    for sym, df in data_by_symbol.items():
        s = compute_signal_frame(df, cfg.strategy)
        a = atr(df, window=14) * cfg.risk.stop_atr_mult
        s = s.merge(a.rename("stop_dist"), left_index=True, right_index=True)
        signals_by_symbol[sym] = s

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
    sizing_log: List[dict] = []

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

        # Stop distances for BUY fills come from *yesterday's* signal row (as-of prior close).
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
                "stop_distance": f.stop_distance,
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

        # Stop distance as-of today (used for sizing orders that execute next open)
        stop_dist_today: Dict[str, float] = {}
        for sym in cfg.universe:
            sdf = signals_by_symbol[sym]
            r = sdf.loc[sdf["Date"] == asof_ts]
            if r.empty:
                continue
            sd = r.iloc[0].get("stop_dist")
            stop_dist_today[sym] = float(sd) if pd.notna(sd) else 0.0

        # Convert weights to target quantities (audit sizing)
        target_qty: Dict[str, int] = {}
        for sym, w in tgt_w.items():
            q, audit = _calc_target_qty(
                symbol=sym,
                weight=w,
                nav=nav,
                close_px=close_prices[sym],
                next_open_px=float(market.iloc[idx + 1][f"{sym}_Open"]),
                stop_dist=stop_dist_today.get(sym, 0.0),
                risk_cfg=cfg.risk,
                exposure_factor=risk_state.exposure_factor,
                slippage_bps_=cfg.broker.slippage_bps,
                commission_bps_=cfg.broker.commission_bps,
                available_cash=broker.state.cash.available,
            )
            target_qty[sym] = q
            audit["asof_day"] = fmt_yyyy_mm_dd(today)
            audit["exec_day"] = fmt_yyyy_mm_dd(next_day)
            sizing_log.append(audit)

        # Build orders from current -> target with execution constraints (T1.4)
        orders_next: List[Order] = []
        lot = int(cfg.broker.lot_size)
        min_notional = float(cfg.broker.min_trade_notional)
        max_turnover = float(cfg.broker.max_daily_turnover)
        gap_th = float(cfg.broker.gap_block_threshold)

        # 1) Sells first (always allowed for reduce/close), lot/min-notional constrained
        for sym in cfg.universe:
            cur = broker.state.position_qty(sym)
            tgt = target_qty.get(sym, 0)
            if tgt >= cur:
                continue
            qty = cur - tgt
            if lot > 1:
                q2 = (qty // lot) * lot
                if q2 != qty:
                    if q2 > 0:
                        orders_next.append(Order(day=next_day, symbol=sym, side="SELL", qty=q2, reason="rounded_lot"))
                    else:
                        orders_next.append(Order(day=next_day, symbol=sym, side="SELL", qty=0, reason="below_min_notional"))
                    qty = q2
            if qty > 0:
                exp_px = float(market.iloc[idx + 1][f"{sym}_Open"]) * (1.0 - bps(cfg.broker.slippage_bps))
                if qty * exp_px < min_notional:
                    orders_next.append(Order(day=next_day, symbol=sym, side="SELL", qty=0, reason="below_min_notional"))
                else:
                    orders_next.append(Order(day=next_day, symbol=sym, side="SELL", qty=qty, reason="rebalance"))

        # 2) Buys with gap block, lot sizing, min notional, and max daily turnover cap
        # turnover budget based on today's NAV (prev day for execution day)
        turnover_budget = nav * max_turnover
        used_buy_notional = 0.0
        buy_syms = [sym for sym in cfg.universe if target_qty.get(sym, 0) > broker.state.position_qty(sym)]
        for sym in sorted(buy_syms):
            cur = broker.state.position_qty(sym)
            raw_qty = target_qty.get(sym, 0) - cur
            if raw_qty <= 0:
                continue

            close_px = close_prices[sym]
            next_open_px = float(market.iloc[idx + 1][f"{sym}_Open"])
            gap = abs(next_open_px / close_px - 1.0) if close_px > 0 else 0.0
            if gap > gap_th:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=0, reason="blocked_gap"))
                continue

            qty = raw_qty
            reason = "rebalance"

            if lot > 1:
                q2 = (qty // lot) * lot
                if q2 != qty:
                    reason = "rounded_lot" if q2 > 0 else "below_min_notional"
                qty = q2
            if qty <= 0:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=0, reason=reason))
                continue

            exp_buy_px = next_open_px * (1.0 + bps(cfg.broker.slippage_bps))
            est_notional = qty * exp_buy_px
            if est_notional < min_notional:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=0, reason="below_min_notional"))
                continue

            remain_budget = turnover_budget - used_buy_notional
            if remain_budget < -1e-9:
                remain_budget = 0.0
            max_qty_turnover = int((remain_budget + 1e-9) // exp_buy_px) if exp_buy_px > 0 else 0
            if qty > max_qty_turnover:
                qty = max_qty_turnover
                reason = "blocked_turnover"

            if lot > 1:
                q3 = (qty // lot) * lot
                if q3 != qty:
                    reason = "rounded_lot" if q3 > 0 else "blocked_turnover"
                qty = q3

            if qty <= 0:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=0, reason="blocked_turnover"))
                continue

            est_notional = qty * exp_buy_px
            if est_notional < min_notional:
                orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=0, reason="below_min_notional"))
                continue

            used_buy_notional += est_notional
            orders_next.append(Order(day=next_day, symbol=sym, side="BUY", qty=qty, reason=reason))

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
        "data_quality": asdict(cfg.data_quality),
    }
    write_json(run_dir / "config.json", cfg_payload)

    write_csv(run_dir / "orders.csv", orders_log, ["day", "symbol", "side", "qty", "reason"])
    write_csv(
        run_dir / "fills.csv",
        fills_log,
        ["day", "symbol", "side", "qty", "price", "notional", "commission", "slippage_bps", "stop_distance", "reason"],
    )
    write_csv(
        run_dir / "equity_curve.csv",
        equity_log,
        [
            "day",
            "nav",
            "peak",
            "drawdown",
            "risk_mode",
            "exposure_factor",
            "settled_cash",
            "reserved_cash",
            "available_cash",
            "pending_cash",
        ],
    )

    # Sizing audit trail (T1.2)
    if sizing_log:
        # stable column order for QA
        cols = [
            "asof_day",
            "exec_day",
            "symbol",
            "weight",
            "nav",
            "exposure_factor",
            "available_cash",
            "close_px",
            "next_open_px",
            "exec_px",
            "slippage_bps",
            "commission_bps",
            "position_cap",
            "max_notional",
            "desired_notional",
            "desired_notional_capped",
            "desired_qty_by_weight",
            "max_cap_qty",
            "per_trade_risk",
            "risk_budget",
            "stop_dist",
            "shares_by_risk",
            "shares_by_cash",
            "final_target_qty",
        ]
        write_csv(run_dir / "sizing_audit.csv", sizing_log, cols)

    return run_dir
