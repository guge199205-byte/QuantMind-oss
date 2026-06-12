"""Minimal A-share broker simulator.

Day-2 scope:
- T+1 sell rule (a position acquired today cannot be sold today)
- Per-trade commission, slippage on entry, sell-side tax + transfer fee
- 100-share lot size for A-share (rounded down)
- Order intents (buy/sell/set_position/set_target_holdings) → list of Trade
- Mark-to-market at close

The broker is intentionally engine-agnostic — the runner feeds it a
``DataProvider`` for price/snapshot lookups. Tests use ``InMemoryProvider``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..runner.result_collector import EquityPoint, PositionSnapshot, TradeRecord
from ..sdk.context import Context, OrderIntent
from ..sdk.position import Position

logger = logging.getLogger(__name__)

LOT_SIZE = 100  # A-share standard lot


@dataclass
class _Lot:
    """Internal record of a single buy lot — used for FIFO accounting."""

    qty: int
    cost: float
    bought_on: pd.Timestamp


@dataclass
class _Holding:
    symbol: str
    lots: list[_Lot] = field(default_factory=list)
    total_qty: int = 0
    total_cost: float = 0.0
    last_price: float = 0.0
    holding_days: int = 0
    reason: str = ""

    def sellable_qty(self, today: pd.Timestamp) -> int:
        """Qty that can be sold today (T+1: not bought today)."""
        return sum(l.qty for l in self.lots if l.bought_on < today)

    def market_value(self) -> float:
        return self.total_qty * self.last_price


class SimpleBroker:
    """Stateless broker — call ``process_day`` once per trading day."""

    def __init__(
        self,
        ctx: Context,
        provider: Any,
        cash: float,
    ) -> None:
        self._ctx = ctx
        self._provider = provider
        self._cash: float = float(cash)
        self._holdings: dict[str, _Holding] = {}
        self._trades: list[TradeRecord] = []
        self._equity_curve: list[EquityPoint] = []
        self._positions_snap: list[PositionSnapshot] = []
        self._initial_cash = float(cash)
        # Active risk rules per-symbol (registered via ctx.set_stop_loss/...)
        self._stop_loss: dict[str, float] = {}
        self._take_profit: dict[str, float] = {}
        self._max_hold_days: dict[str, int] = {}
        self._account_stop_loss: float | None = None
        self._account_halted: bool = False

    # ------------------------------------------------------------------
    # Pricing helpers
    # ------------------------------------------------------------------
    def _close(self, symbol: str, today: pd.Timestamp) -> float | None:
        try:
            s = self._provider.history(
                symbol=symbol, n=1, field="close", today=today
            )
        except Exception as e:
            logger.debug("history fetch failed %s @ %s: %s", symbol, today, e)
            return None
        if s is None or len(s) == 0:
            return None
        try:
            v = float(s.iloc[-1])
        except Exception:
            return None
        if math.isnan(v) or math.isinf(v) or v <= 0:
            return None
        return v

    def _benchmark_close(self, today: pd.Timestamp) -> float | None:
        try:
            s = self._provider.benchmark_history(self._ctx.benchmark, 1, today)
        except Exception:
            return None
        if s is None or len(s) == 0:
            return None
        try:
            return float(s.iloc[-1])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Order resolution
    # ------------------------------------------------------------------
    def _qty_for_weight(self, weight: float, price: float, equity: float) -> int:
        if price <= 0 or weight <= 0:
            return 0
        target_value = equity * weight
        raw_qty = int(target_value // price)
        return (raw_qty // LOT_SIZE) * LOT_SIZE

    def _execute_buy(
        self,
        symbol: str,
        qty: int,
        price: float,
        today: pd.Timestamp,
        reason: str,
        detail: dict[str, Any],
    ) -> None:
        if qty <= 0 or price <= 0:
            return
        slipped = price * (1 + self._ctx.slippage)
        gross = slipped * qty
        commission = max(gross * self._ctx.commission, 0.0)
        cost = gross + commission
        if cost > self._cash + 1e-6:
            # Cap qty downward to lot multiple that fits
            max_qty = int(self._cash // (slipped * (1 + self._ctx.commission)))
            qty = (max_qty // LOT_SIZE) * LOT_SIZE
            if qty <= 0:
                return
            gross = slipped * qty
            commission = max(gross * self._ctx.commission, 0.0)
            cost = gross + commission
        self._cash -= cost
        h = self._holdings.setdefault(symbol, _Holding(symbol=symbol))
        h.lots.append(_Lot(qty=qty, cost=cost, bought_on=today))
        h.total_qty += qty
        h.total_cost += cost
        h.last_price = price
        h.reason = reason or h.reason
        self._trades.append(
            TradeRecord(
                date=today.strftime("%Y-%m-%d"),
                symbol=symbol,
                direction="BUY",
                price=slipped,
                qty=qty,
                reason=reason,
                detail=dict(detail),
            )
        )

    def _execute_sell(
        self,
        symbol: str,
        qty: int,
        price: float,
        today: pd.Timestamp,
        reason: str,
        detail: dict[str, Any],
    ) -> None:
        h = self._holdings.get(symbol)
        if h is None or h.total_qty <= 0 or qty <= 0 or price <= 0:
            return
        sellable = h.sellable_qty(today)
        qty = min(qty, sellable)
        if qty <= 0:
            return
        slipped = price * (1 - self._ctx.slippage)
        gross = slipped * qty
        commission = max(gross * self._ctx.commission, 0.0)
        tax = gross * self._ctx.tax_sell
        transfer = gross * self._ctx.transfer_fee
        proceeds = gross - commission - tax - transfer
        # FIFO consume lots, but only those bought before today (T+1)
        remaining = qty
        cost_basis_consumed = 0.0
        new_lots: list[_Lot] = []
        for lot in h.lots:
            if remaining <= 0 or lot.bought_on >= today:
                new_lots.append(lot)
                continue
            take = min(lot.qty, remaining)
            cost_basis_consumed += (lot.cost / lot.qty) * take if lot.qty > 0 else 0.0
            remaining -= take
            if take < lot.qty:
                new_lots.append(
                    _Lot(qty=lot.qty - take, cost=lot.cost - (lot.cost / lot.qty) * take, bought_on=lot.bought_on)
                )
        h.lots = new_lots
        h.total_qty -= qty
        h.total_cost -= cost_basis_consumed
        if h.total_qty <= 0:
            self._holdings.pop(symbol, None)
        self._cash += proceeds
        pnl = proceeds - cost_basis_consumed
        self._trades.append(
            TradeRecord(
                date=today.strftime("%Y-%m-%d"),
                symbol=symbol,
                direction="SELL",
                price=slipped,
                qty=qty,
                reason=reason,
                detail=dict(detail),
                pnl=pnl,
            )
        )

    # ------------------------------------------------------------------
    # Per-day pipeline
    # ------------------------------------------------------------------
    def _equity_now(self, today: pd.Timestamp) -> float:
        mv = 0.0
        for h in self._holdings.values():
            p = self._close(h.symbol, today)
            if p is not None:
                h.last_price = p
            mv += h.market_value()
        return self._cash + mv

    def _resolve_orders(
        self,
        orders: list[OrderIntent],
        today: pd.Timestamp,
    ) -> list[tuple[str, str, int, float, str, dict[str, Any]]]:
        """Translate OrderIntent objects into concrete (side, symbol, qty, price, reason, detail) tuples."""
        equity = self._equity_now(today)
        resolved: list[tuple[str, str, int, float, str, dict[str, Any]]] = []
        for o in orders:
            if o.side == "set_target_holdings":
                if not o.targets:
                    continue
                weight = 1.0 / len(o.targets)
                # Sell anything not in target list
                for sym in list(self._holdings.keys()):
                    if sym not in o.targets:
                        h = self._holdings[sym]
                        sellable = h.sellable_qty(today)
                        if sellable > 0:
                            price = self._close(sym, today)
                            if price is not None:
                                resolved.append(
                                    ("sell", sym, sellable, price, o.reason or "rebalance", dict(o.detail))
                                )
                # Then buy missing targets
                for sym in o.targets:
                    price = self._close(sym, today)
                    if price is None:
                        continue
                    cur = self._holdings.get(sym)
                    cur_value = cur.market_value() if cur else 0.0
                    target_value = equity * weight
                    delta = target_value - cur_value
                    if delta > price * LOT_SIZE:
                        raw_qty = int(delta // price)
                        qty = (raw_qty // LOT_SIZE) * LOT_SIZE
                        if qty > 0:
                            resolved.append(
                                ("buy", sym, qty, price, o.reason or "rebalance", dict(o.detail))
                            )
                continue
            if o.side == "set_position":
                price = self._close(o.symbol, today)
                if price is None:
                    continue
                target_qty = self._qty_for_weight(o.weight or 0.0, price, equity)
                cur_qty = self._holdings[o.symbol].total_qty if o.symbol in self._holdings else 0
                delta = target_qty - cur_qty
                if delta > 0:
                    resolved.append(("buy", o.symbol, delta, price, o.reason, dict(o.detail)))
                elif delta < 0:
                    resolved.append(("sell", o.symbol, -delta, price, o.reason, dict(o.detail)))
                continue
            if o.side == "buy":
                price = self._close(o.symbol, today)
                if price is None:
                    continue
                if o.qty is not None:
                    qty = (int(o.qty) // LOT_SIZE) * LOT_SIZE
                else:
                    qty = self._qty_for_weight(o.weight or 0.0, price, equity)
                if qty > 0:
                    resolved.append(("buy", o.symbol, qty, price, o.reason, dict(o.detail)))
                continue
            if o.side == "sell":
                price = self._close(o.symbol, today)
                if price is None:
                    continue
                h = self._holdings.get(o.symbol)
                if h is None:
                    continue
                if o.all:
                    qty = h.sellable_qty(today)
                elif o.qty is not None:
                    qty = min(int(o.qty), h.sellable_qty(today))
                elif o.weight is not None:
                    qty = int(h.total_qty * o.weight)
                    qty = (qty // LOT_SIZE) * LOT_SIZE
                    qty = min(qty, h.sellable_qty(today))
                else:
                    qty = 0
                if qty > 0:
                    resolved.append(("sell", o.symbol, qty, price, o.reason, dict(o.detail)))
        return resolved

    # ------------------------------------------------------------------
    # Risk rules
    # ------------------------------------------------------------------
    def register_risk_rules(self, rules: list[Any]) -> None:
        """Absorb RiskRule objects drained from ctx for the day.

        Stores them on the broker; auto-sells trigger at the start of the
        next ``process_day`` call before user orders.
        """
        for rule in rules:
            kind = getattr(rule, "kind", None)
            sym = getattr(rule, "symbol", None)
            value = getattr(rule, "value", None)
            if kind == "stop_loss" and sym is not None:
                self._stop_loss[sym] = float(value)
            elif kind == "take_profit" and sym is not None:
                self._take_profit[sym] = float(value)
            elif kind == "max_holding_days" and sym is not None:
                self._max_hold_days[sym] = int(value)
            elif kind == "account_stop_loss":
                self._account_stop_loss = float(value)

    def _enforce_risk(self, today: pd.Timestamp) -> list[tuple[str, str, int, float, str, dict[str, Any]]]:
        """Return forced-sell orders for any holding that breached a rule.

        Sells use today's close as the trigger price; subject to T+1 (sellable_qty).
        """
        if self._account_halted:
            return []
        forced: list[tuple[str, str, int, float, str, dict[str, Any]]] = []

        # Account-level stop loss check first
        if self._account_stop_loss is not None and self._initial_cash > 0:
            equity = self._equity_now(today)
            ret = equity / self._initial_cash - 1
            if ret <= self._account_stop_loss:
                self._account_halted = True
                for sym, h in list(self._holdings.items()):
                    sellable = h.sellable_qty(today)
                    if sellable <= 0:
                        continue
                    price = self._close(sym, today)
                    if price is None:
                        continue
                    forced.append(
                        ("sell", sym, sellable, price, "account_stop_loss",
                         {"account_ret": ret, "threshold": self._account_stop_loss})
                    )
                return forced

        for sym, h in list(self._holdings.items()):
            sellable = h.sellable_qty(today)
            if sellable <= 0:
                continue
            price = self._close(sym, today)
            if price is None or h.total_qty <= 0:
                continue
            avg_cost = h.total_cost / h.total_qty if h.total_qty > 0 else 0.0
            if avg_cost <= 0:
                continue
            ret = price / avg_cost - 1

            sl = self._stop_loss.get(sym)
            tp = self._take_profit.get(sym)
            mhd = self._max_hold_days.get(sym)

            if sl is not None and ret <= sl:
                forced.append(
                    ("sell", sym, sellable, price, "stop_loss",
                     {"ret": ret, "threshold": sl, "avg_cost": avg_cost})
                )
                continue
            if tp is not None and ret >= tp:
                forced.append(
                    ("sell", sym, sellable, price, "take_profit",
                     {"ret": ret, "threshold": tp, "avg_cost": avg_cost})
                )
                continue
            if mhd is not None and h.holding_days >= mhd:
                forced.append(
                    ("sell", sym, sellable, price, "max_holding_days",
                     {"holding_days": h.holding_days, "threshold": mhd})
                )
        return forced

    def process_day(
        self,
        today: pd.Timestamp,
        orders: list[OrderIntent],
    ) -> None:
        # Increment holding_days for everything held entering today
        for h in self._holdings.values():
            h.holding_days += 1

        # 1) Enforce risk rules first (forced sells take precedence over user orders)
        forced = self._enforce_risk(today)
        for side, sym, qty, price, reason, detail in forced:
            if side == "sell":
                self._execute_sell(sym, qty, price, today, reason, detail)
        # If a holding was fully closed by risk, drop its rules
        for sym in list(self._stop_loss.keys()):
            if sym not in self._holdings:
                self._stop_loss.pop(sym, None)
        for sym in list(self._take_profit.keys()):
            if sym not in self._holdings:
                self._take_profit.pop(sym, None)
        for sym in list(self._max_hold_days.keys()):
            if sym not in self._holdings:
                self._max_hold_days.pop(sym, None)

        # 2) Resolve and execute user orders (skip if account-halted)
        if not self._account_halted:
            resolved = self._resolve_orders(orders, today)
            # Sells before buys to free up cash
            for side, sym, qty, price, reason, detail in resolved:
                if side == "sell":
                    self._execute_sell(sym, qty, price, today, reason, detail)
            for side, sym, qty, price, reason, detail in resolved:
                if side == "buy":
                    self._execute_buy(sym, qty, price, today, reason, detail)

        # Mark-to-market
        for h in self._holdings.values():
            p = self._close(h.symbol, today)
            if p is not None:
                h.last_price = p

        equity = self._cash + sum(h.market_value() for h in self._holdings.values())
        bench = self._benchmark_close(today)
        self._equity_curve.append(
            EquityPoint(
                date=today.strftime("%Y-%m-%d"),
                value=float(equity),
                benchmark=float(bench) if bench is not None else None,
            )
        )

        # Sync ctx-side positions for next bar
        self._ctx._update_cash_equity(self._cash, equity)
        # Clear ctx positions and re-emit current ones
        for sym in list(self._ctx._positions.keys()):
            if sym not in self._holdings:
                self._ctx._set_position(Position(symbol=sym, qty=0))
        for h in self._holdings.values():
            self._ctx._set_position(
                Position(
                    symbol=h.symbol,
                    qty=h.total_qty,
                    cost=h.total_cost,
                    market_value=h.market_value(),
                    last_price=h.last_price,
                    holding_days=h.holding_days,
                    reason=h.reason,
                )
            )

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self._cash

    @property
    def equity(self) -> float:
        return self._cash + sum(h.market_value() for h in self._holdings.values())

    @property
    def trades(self) -> list[TradeRecord]:
        return list(self._trades)

    @property
    def equity_curve(self) -> list[EquityPoint]:
        return list(self._equity_curve)

    def positions_snapshot(self, date: pd.Timestamp) -> list[PositionSnapshot]:
        rows: list[PositionSnapshot] = []
        for h in self._holdings.values():
            mv = h.market_value()
            pnl_pct = 0.0
            if h.total_cost > 0:
                pnl_pct = (mv - h.total_cost) / h.total_cost
            rows.append(
                PositionSnapshot(
                    date=date.strftime("%Y-%m-%d"),
                    symbol=h.symbol,
                    qty=h.total_qty,
                    cost=h.total_cost,
                    market_value=mv,
                    pnl_pct=pnl_pct,
                )
            )
        return rows
