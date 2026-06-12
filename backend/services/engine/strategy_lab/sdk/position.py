"""Position — single-stock holding view exposed to user code via ctx.position(symbol)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Position:
    """A single-stock position snapshot.

    Read-only from user code. The runner mutates these via the broker simulator.

    Attributes mirror §4.3.5 of Strategy_Lab规范.md.
    """

    symbol: str
    qty: int = 0
    cost: float = 0.0
    market_value: float = 0.0
    last_price: float = 0.0
    holding_days: int = 0
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_holding_days: int | None = None

    @property
    def pnl(self) -> float:
        if self.qty <= 0:
            return 0.0
        return self.market_value - self.cost

    @property
    def pnl_pct(self) -> float:
        if self.qty <= 0 or self.cost <= 0:
            return 0.0
        return (self.market_value - self.cost) / self.cost

    @property
    def avg_cost(self) -> float:
        if self.qty <= 0:
            return 0.0
        return self.cost / self.qty

    def __bool__(self) -> bool:
        return self.qty > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "cost": self.cost,
            "avg_cost": self.avg_cost,
            "market_value": self.market_value,
            "last_price": self.last_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "holding_days": self.holding_days,
            "reason": self.reason,
            "detail": self.detail,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_holding_days": self.max_holding_days,
        }
