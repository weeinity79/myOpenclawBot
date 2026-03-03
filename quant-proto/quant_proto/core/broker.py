from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple


@dataclass
class Order:
    day: date              # trade date (execution at open of this date)
    symbol: str
    side: str              # 'BUY' or 'SELL'
    qty: int
    reason: str = ""


@dataclass
class Fill:
    day: date
    symbol: str
    side: str
    qty: int
    price: float
    notional: float
    commission: float
    slippage_bps: float
    reason: str = ""


@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_price: float = 0.0
    # v1 stop model stored as distance (ATR*2) computed at entry
    stop_distance: float = 0.0


@dataclass
class CashLedger:
    """Cash account model with simplified settlement.

    - settled: cash you can spend today
    - pending: unsettled cash that will become settled on/after avail_day
    - reserved: cash earmarked for today's BUY orders (intraday reservation)

    Note: reserved is reset by the simulator each trading day.
    """

    settled: float
    pending: List[Tuple[date, float]] = field(default_factory=list)
    reserved: float = 0.0

    def process_settlements(self, today: date) -> None:
        newly_settled: float = 0.0
        remain: List[Tuple[date, float]] = []
        for avail_day, amt in self.pending:
            if avail_day <= today:
                newly_settled += amt
            else:
                remain.append((avail_day, amt))
        self.pending = remain
        self.settled += newly_settled

    def add_unsettled(self, avail_day: date, amt: float) -> None:
        self.pending.append((avail_day, amt))

    @property
    def available(self) -> float:
        return max(self.settled - self.reserved, 0.0)

    def reset_reserved(self) -> None:
        self.reserved = 0.0


@dataclass
class BrokerConfig:
    slippage_bps: float = 5.0
    commission_bps: float = 1.0
    t_plus_1: bool = True


@dataclass
class BrokerState:
    cash: CashLedger
    positions: Dict[str, Position] = field(default_factory=dict)

    def position_qty(self, symbol: str) -> int:
        return self.positions.get(symbol, Position(symbol)).qty


def bps(x: float) -> float:
    return x / 10_000.0


class Broker:
    def __init__(self, cfg: BrokerConfig, init_cash: float = 100_000.0):
        self.cfg = cfg
        self.state = BrokerState(cash=CashLedger(settled=float(init_cash)))

    def process_settlements(self, today: date) -> None:
        self.state.cash.process_settlements(today)

    def reset_reserved(self) -> None:
        self.state.cash.reset_reserved()

    def equity(self, prices: Dict[str, float]) -> float:
        """Total equity = settled + pending + positions marked to prices."""
        pos_val = 0.0
        for sym, pos in self.state.positions.items():
            if pos.qty == 0:
                continue
            px = prices.get(sym)
            if px is None:
                continue
            pos_val += pos.qty * float(px)
        pending_total = sum(amt for _, amt in self.state.cash.pending)
        return self.state.cash.settled + pending_total + pos_val

    def _commission(self, notional: float) -> float:
        return abs(notional) * bps(self.cfg.commission_bps)

    def _buy_total_cost(self, qty: int, price: float) -> float:
        notional = qty * price
        return notional + self._commission(notional)

    def _apply_fill(self, fill: Fill, today: date) -> None:
        sym = fill.symbol
        pos = self.state.positions.get(sym, Position(sym))

        if fill.side == "BUY":
            cost = fill.notional + fill.commission
            # release reservation (best-effort; reservation is approximate)
            self.state.cash.reserved = max(self.state.cash.reserved - cost, 0.0)
            self.state.cash.settled -= cost

            new_qty = pos.qty + fill.qty
            if new_qty <= 0:
                pos.qty = 0
                pos.avg_price = 0.0
            else:
                pos.avg_price = ((pos.avg_price * pos.qty) + (fill.price * fill.qty)) / new_qty
                pos.qty = new_qty
        else:
            proceeds = fill.notional - fill.commission
            avail = today
            if self.cfg.t_plus_1:
                # naive: next calendar day; simulator settles on trading days only
                from datetime import timedelta

                avail = today + timedelta(days=1)
            self.state.cash.add_unsettled(avail, proceeds)
            pos.qty -= fill.qty
            if pos.qty <= 0:
                pos.qty = 0
                pos.avg_price = 0.0
                pos.stop_distance = 0.0

        self.state.positions[sym] = pos

    def execute_orders(
        self,
        today: date,
        open_prices: Dict[str, float],
        orders: List[Order],
        stop_dist_by_symbol: Optional[Dict[str, float]] = None,
    ) -> List[Fill]:
        """Execute market orders at open with slippage + commission.

        - Sells execute first.
        - Buys require sufficient **available settled cash** (settled - reserved).
          If not enough, buys are down-sized.
        """
        fills: List[Fill] = []

        sells = [o for o in orders if o.side == "SELL" and o.qty > 0]
        buys = [o for o in orders if o.side == "BUY" and o.qty > 0]

        # Execute sells
        for o in sells:
            pos_qty = self.state.position_qty(o.symbol)
            qty = min(pos_qty, o.qty)
            if qty <= 0:
                continue
            px0 = float(open_prices[o.symbol])
            px = px0 * (1.0 - bps(self.cfg.slippage_bps))
            notional = qty * px
            comm = self._commission(notional)
            fill = Fill(
                day=today,
                symbol=o.symbol,
                side="SELL",
                qty=qty,
                price=px,
                notional=notional,
                commission=comm,
                slippage_bps=self.cfg.slippage_bps,
                reason=o.reason,
            )
            self._apply_fill(fill, today)
            fills.append(fill)

        # Reserve + execute buys sequentially using available settled cash.
        for o in buys:
            px0 = float(open_prices[o.symbol])
            px = px0 * (1.0 + bps(self.cfg.slippage_bps))

            # first reserve as much as possible for requested qty
            max_affordable_qty = int(self.state.cash.available // (px * (1.0 + bps(self.cfg.commission_bps))))
            qty = min(o.qty, max_affordable_qty)
            if qty <= 0:
                continue

            est_cost = self._buy_total_cost(qty, px)
            self.state.cash.reserved += est_cost

            notional = qty * px
            comm = self._commission(notional)
            fill = Fill(
                day=today,
                symbol=o.symbol,
                side="BUY",
                qty=qty,
                price=px,
                notional=notional,
                commission=comm,
                slippage_bps=self.cfg.slippage_bps,
                reason=o.reason,
            )
            self._apply_fill(fill, today)

            if stop_dist_by_symbol is not None:
                pos = self.state.positions[o.symbol]
                sd = float(stop_dist_by_symbol.get(o.symbol, 0.0))
                pos.stop_distance = sd
                self.state.positions[o.symbol] = pos

            fills.append(fill)

        return fills
