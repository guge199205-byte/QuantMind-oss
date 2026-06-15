"""Context — the single object passed to setup / on_universe / on_bar.

This is the user-facing API surface. The Day-1 version implements the
attribute model + parameter declarations + recording of orders and risk
rules; the actual broker / data layer lives in runner/* and engine/*
(Days 2-3). User code that only references the SDK never imports those
internals, which is what lets us swap engines later.

Spec: §4 of docs/Strategy_Lab规范.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

import pandas as pd

from .position import Position

# ---------------------------------------------------------------------------
# Attribute schema — declared centrally so we can validate user code.
# ---------------------------------------------------------------------------
_ALLOWED_UNIVERSES: frozenset[str] = frozenset(
    {
        "csi300",
        "csi500",
        "csi800",
        "csi1000",
        "hs300_ext",
        "all_a",
        "hk_main",
        "us_sp500",
    }
)
_ALLOWED_EXECUTION_MODELS: frozenset[str] = frozenset({"a_share_strict", "simple"})
_ALLOWED_ENGINES: frozenset[str] = frozenset({"qlib"})

_DEFAULTS: dict[str, Any] = {
    "universe": None,
    "start": None,
    "end": None,
    "cash": None,
    "benchmark": "SH000300",
    "commission": 0.0003,
    "slippage": 0.0005,
    "tax_sell": 0.0005,
    "transfer_fee": 0.00001,
    "execution_model": "a_share_strict",
    "max_position_per_stock": 0.10,
    "max_positions": 10,
    "engine": "qlib",
    "freq": "day",
}


def _coerce_date(val: Any) -> pd.Timestamp:
    if isinstance(val, pd.Timestamp):
        return val
    if isinstance(val, datetime):
        return pd.Timestamp(val)
    return pd.Timestamp(str(val))


# ---------------------------------------------------------------------------
# Order / risk records — the runner consumes these.
# ---------------------------------------------------------------------------
@dataclass
class OrderIntent:
    symbol: str
    side: str  # "buy" / "sell" / "set_position" / "set_target_holdings"
    weight: float | None = None
    qty: int | None = None
    all: bool = False
    targets: list[str] = field(default_factory=list)
    target_weight_mode: str = "equal"
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskRule:
    symbol: str | None
    kind: str  # "stop_loss" / "take_profit" / "account_stop_loss" / "max_holding_days"
    value: float | int


@dataclass
class ParamSpec:
    name: str
    choices: list[Any]
    default: Any


@dataclass
class StatsView:
    n_trades: int = 0
    n_buy: int = 0
    n_sell: int = 0
    cum_return: float = 0.0
    max_drawdown: float = 0.0


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
class Context:
    """The single object passed to setup / on_bar / on_universe.

    Day-1 scope: attributes + parameter declaration + order/risk recording +
    log/plot collection. The data layer (history/feature/snapshot) and broker
    layer (buy/sell execution) raise NotImplementedError until wired by the
    runner — tests inject stubs.
    """

    # Slots-ish: declare allowed runtime fields explicitly. We DON'T use
    # __slots__ because user code may stash bookkeeping on ctx; instead we
    # validate writes through __setattr__ for the "config" attributes only.

    _CONFIG_KEYS: frozenset[str] = frozenset(_DEFAULTS.keys())
    _RESERVED_KEYS: frozenset[str] = frozenset(
        {
            "_params",
            "_param_values",
            "_orders",
            "_risk_rules",
            "_logs",
            "_plot_lines",
            "_plot_markers",
            "_positions",
            "_equity",
            "_today",
            "_data_provider",
            "_broker",
            "_now_index",
            "_dirty",
            "_drawn_lines",
            "stats",
        }
    )

    def __init__(self) -> None:
        # Use object.__setattr__ to bypass our own validation hook.
        for k, v in _DEFAULTS.items():
            object.__setattr__(self, k, v)

        object.__setattr__(self, "_params", {})  # name -> ParamSpec
        object.__setattr__(self, "_param_values", {})  # name -> current value
        object.__setattr__(self, "_orders", [])
        object.__setattr__(self, "_risk_rules", [])
        object.__setattr__(self, "_logs", [])
        object.__setattr__(self, "_plot_lines", [])
        object.__setattr__(self, "_plot_markers", [])
        object.__setattr__(self, "_positions", {})  # symbol -> Position
        object.__setattr__(self, "_equity", 0.0)
        object.__setattr__(self, "_today", None)
        object.__setattr__(self, "_data_provider", None)
        object.__setattr__(self, "_broker", None)
        object.__setattr__(self, "_now_index", 0)
        object.__setattr__(self, "_dirty", False)
        object.__setattr__(self, "_drawn_lines", {})
        object.__setattr__(self, "stats", StatsView())

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._CONFIG_KEYS:
            self._validate_config(key, value)
            object.__setattr__(self, key, value)
            object.__setattr__(self, "_dirty", True)
            return
        if key in self._RESERVED_KEYS:
            object.__setattr__(self, key, value)
            return
        # User scratch space — allowed, but discourage by name conflict.
        object.__setattr__(self, key, value)

    @staticmethod
    def _validate_config(key: str, value: Any) -> None:
        if value is None:
            return
        if key == "universe":
            if isinstance(value, str):
                if value not in _ALLOWED_UNIVERSES:
                    raise ValueError(
                        f"universe='{value}' not supported. "
                        f"choose from {sorted(_ALLOWED_UNIVERSES)} or pass list[str]."
                    )
            elif isinstance(value, (list, tuple, set)):
                if not all(isinstance(s, str) and s for s in value):
                    raise ValueError("universe list must contain non-empty strings")
            else:
                raise TypeError(f"universe must be str or list[str], got {type(value).__name__}")
        elif key in {"start", "end"}:
            try:
                _coerce_date(value)
            except Exception as e:
                raise ValueError(f"{key} must be a date-like (YYYY-MM-DD): {e}") from e
        elif key == "cash":
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError("cash must be a positive number")
        elif key == "benchmark":
            if not isinstance(value, str) or not value:
                raise ValueError("benchmark must be non-empty string")
        elif key in {"commission", "slippage", "tax_sell", "transfer_fee"}:
            if not isinstance(value, (int, float)) or not (0.0 <= value < 0.1):
                raise ValueError(f"{key} must be a float in [0, 0.1)")
        elif key == "execution_model":
            if value not in _ALLOWED_EXECUTION_MODELS:
                raise ValueError(
                    f"execution_model='{value}' not supported. "
                    f"choose from {sorted(_ALLOWED_EXECUTION_MODELS)}"
                )
        elif key == "max_position_per_stock":
            if not isinstance(value, (int, float)) or not (0.0 < value <= 1.0):
                raise ValueError("max_position_per_stock must be in (0, 1]")
        elif key == "max_positions":
            if not isinstance(value, int) or value <= 0:
                raise ValueError("max_positions must be a positive integer")
        elif key == "engine":
            if value not in _ALLOWED_ENGINES:
                raise ValueError(
                    f"engine='{value}' not supported. v1 is {sorted(_ALLOWED_ENGINES)}"
                )
        elif key == "freq":
            if value not in {"day", "30min", "5min"}:
                raise ValueError("freq must be 'day' / '30min' / '5min'")

    def assert_ready(self) -> None:
        """Validate after setup() — required fields filled."""
        missing = [k for k in ("universe", "start", "end", "cash") if getattr(self, k) is None]
        if missing:
            raise ValueError(f"setup(ctx) missing required: {missing}")
        s = _coerce_date(self.start)
        e = _coerce_date(self.end)
        if s >= e:
            raise ValueError(f"start ({self.start}) must be before end ({self.end})")

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------
    def param(
        self,
        name: str,
        choices: Iterable[Any] | None = None,
        default: Any = None,
    ) -> Any:
        """Declare a tunable parameter and return its current value.

        First call registers the param spec. Subsequent calls just look it up
        (so the line ``window = ctx.param('window', range(10,50,5), default=22)``
        works both during the first sweep run and inside any rerun).
        """
        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError(f"param name '{name}' must be a valid Python identifier")

        if name in self._params:
            return self._param_values.get(name, self._params[name].default)

        if choices is None:
            choices_list: list[Any] = []
        else:
            choices_list = list(choices)
        if default is None:
            if not choices_list:
                raise ValueError(f"param '{name}' needs either choices or a default")
            default = choices_list[0]

        spec = ParamSpec(name=name, choices=choices_list, default=default)
        self._params[name] = spec
        if name not in self._param_values:
            self._param_values[name] = default
        return self._param_values[name]

    def set_param(self, name: str, value: Any) -> None:
        """Runner uses this to inject the next sweep point."""
        if name not in self._params:
            raise KeyError(f"param '{name}' not declared via ctx.param()")
        self._param_values[name] = value

    @property
    def params(self) -> dict[str, ParamSpec]:
        return dict(self._params)

    @property
    def param_values(self) -> dict[str, Any]:
        return dict(self._param_values)

    # ------------------------------------------------------------------
    # Data — actual fetch deferred to the data provider injected by runner.
    # ------------------------------------------------------------------
    def _require_provider(self) -> Any:
        if self._data_provider is None:
            raise RuntimeError(
                "Data provider not attached. "
                "(Are you running the script outside the Strategy Lab runner?)"
            )
        return self._data_provider

    def history(
        self,
        symbol: str | None = None,
        n: int = 20,
        field: str = "close",
        fields: Sequence[str] | None = None,
        symbols: Sequence[str] | None = None,
    ) -> pd.Series | pd.DataFrame:
        provider = self._require_provider()
        return provider.history(
            symbol=symbol, n=n, field=field, fields=fields, symbols=symbols, today=self._today
        )

    def feature(self, symbol: str, name: str, n: int = 1) -> float | pd.Series:
        provider = self._require_provider()
        return provider.feature(symbol=symbol, name=name, n=n, today=self._today)

    def list_features(self) -> list[str]:
        provider = self._require_provider()
        return provider.list_features()

    def snapshot(
        self,
        date: Any | None = None,
        symbols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        provider = self._require_provider()
        return provider.snapshot(date=date or self._today, symbols=symbols)

    def benchmark_history(self, n: int = 20) -> pd.Series:
        provider = self._require_provider()
        return provider.benchmark_history(symbol=self.benchmark, n=n, today=self._today)

    # ------------------------------------------------------------------
    # Orders — recorded; runner replays them after the hook returns.
    # ------------------------------------------------------------------
    def buy(
        self,
        symbol: str,
        weight: float | None = None,
        qty: int | None = None,
        reason: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        if weight is None and qty is None:
            raise ValueError("buy() requires either weight= or qty=")
        if weight is not None and not (0 < weight <= 1.0):
            raise ValueError(f"weight must be in (0, 1], got {weight}")
        if qty is not None and qty <= 0:
            raise ValueError(f"qty must be positive, got {qty}")
        self._orders.append(
            OrderIntent(
                symbol=symbol, side="buy", weight=weight, qty=qty,
                reason=reason, detail=dict(detail or {}),
            )
        )

    def sell(
        self,
        symbol: str,
        weight: float | None = None,
        qty: int | None = None,
        all: bool = False,
        reason: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        if not all and weight is None and qty is None:
            raise ValueError("sell() requires weight=, qty=, or all=True")
        self._orders.append(
            OrderIntent(
                symbol=symbol, side="sell", weight=weight, qty=qty, all=all,
                reason=reason, detail=dict(detail or {}),
            )
        )

    def set_position(
        self,
        symbol: str,
        weight: float,
        reason: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        if not (0 <= weight <= 1.0):
            raise ValueError(f"weight must be in [0, 1], got {weight}")
        self._orders.append(
            OrderIntent(
                symbol=symbol, side="set_position", weight=weight,
                reason=reason, detail=dict(detail or {}),
            )
        )

    def set_target_holdings(
        self,
        symbols: Sequence[str],
        weight: str = "equal",
        reason: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        if weight != "equal":
            raise NotImplementedError("Only weight='equal' supported in v1")
        if not isinstance(symbols, (list, tuple)):
            raise TypeError("symbols must be list/tuple")
        clean = [s for s in symbols if s]
        if len(clean) > self.max_positions:
            clean = clean[: self.max_positions]
        self._orders.append(
            OrderIntent(
                symbol="*", side="set_target_holdings", targets=list(clean),
                target_weight_mode=weight, reason=reason, detail=dict(detail or {}),
            )
        )

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------
    def set_stop_loss(self, symbol: str, pct: float) -> None:
        if not (-0.99 < pct < 0):
            raise ValueError(f"stop_loss pct must be in (-0.99, 0), got {pct}")
        self._risk_rules.append(RiskRule(symbol=symbol, kind="stop_loss", value=pct))
        if symbol in self._positions:
            self._positions[symbol].stop_loss_pct = pct

    def set_take_profit(self, symbol: str, pct: float) -> None:
        if not (0 < pct < 10):
            raise ValueError(f"take_profit pct must be in (0, 10), got {pct}")
        self._risk_rules.append(RiskRule(symbol=symbol, kind="take_profit", value=pct))
        if symbol in self._positions:
            self._positions[symbol].take_profit_pct = pct

    def set_account_stop_loss(self, pct: float) -> None:
        if not (-0.99 < pct < 0):
            raise ValueError(f"account_stop_loss pct must be in (-0.99, 0), got {pct}")
        self._risk_rules.append(RiskRule(symbol=None, kind="account_stop_loss", value=pct))

    def set_max_holding_days(self, symbol: str, days: int) -> None:
        if not isinstance(days, int) or days <= 0:
            raise ValueError("max_holding_days must be a positive int")
        self._risk_rules.append(RiskRule(symbol=symbol, kind="max_holding_days", value=days))
        if symbol in self._positions:
            self._positions[symbol].max_holding_days = days

    # ------------------------------------------------------------------
    # Position queries
    # ------------------------------------------------------------------
    def position(self, symbol: str) -> Position:
        return self._positions.get(symbol, Position(symbol=symbol))

    def positions(self) -> pd.DataFrame:
        if not self._positions:
            return pd.DataFrame(
                columns=[
                    "symbol", "qty", "cost", "avg_cost", "market_value",
                    "last_price", "pnl", "pnl_pct", "holding_days", "reason",
                ]
            )
        rows = [p.to_dict() for p in self._positions.values() if p.qty > 0]
        return pd.DataFrame(rows)

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def today(self) -> pd.Timestamp | None:
        return self._today

    # ------------------------------------------------------------------
    # Tooling — log / plot / heuristics
    # ------------------------------------------------------------------
    def log(self, msg: Any, level: str = "info") -> None:
        if level not in {"debug", "info", "warning", "error"}:
            raise ValueError(f"unknown log level: {level}")
        self._logs.append(
            {
                "level": level,
                "ts": self._today.isoformat() if self._today is not None else None,
                "msg": str(msg),
            }
        )

    def plot_line(self, name: str, value: float, symbol: str | None = None) -> None:
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        if math.isnan(v) or math.isinf(v):
            return
        self._plot_lines.append(
            {
                "name": name,
                "symbol": symbol,
                "ts": self._today.isoformat() if self._today is not None else None,
                "value": v,
            }
        )

    def plot_marker(
        self,
        symbol: str,
        type: str = "alert",
        text: str = "",
        price: float | None = None,
    ) -> None:
        self._plot_markers.append(
            {
                "symbol": symbol,
                "type": type,
                "text": text,
                "price": price,
                "ts": self._today.isoformat() if self._today is not None else None,
            }
        )

    def drawn_line(self, name: str, default: float | None = None) -> float | None:
        """Read a price-level line drawn on the K-line UI.

        Returns the latest price the user dropped on the chart for ``name``,
        or ``default`` if the user has not drawn one. The runner injects values
        via the request body (key: ``drawn_lines``); for backtests run without
        the UI this method always returns ``default``.

        Example:
            stop = ctx.drawn_line('stop_loss', default=0.0)
            if stop and price < stop:
                ctx.sell(symbol, qty=100, reason='manual stop')
        """
        if not isinstance(name, str) or not name:
            return default
        v = self._drawn_lines.get(name)
        if v is None:
            return default
        try:
            f = float(v)
        except (TypeError, ValueError):
            return default
        if math.isnan(f) or math.isinf(f):
            return default
        return f

    # ------------------------------------------------------------------
    # Helpers — wired by runner; safe stubs in tests
    # ------------------------------------------------------------------
    def is_st(self, symbol: str) -> bool:
        provider = self._require_provider()
        if hasattr(provider, "is_st"):
            return bool(provider.is_st(symbol, today=self._today))
        return False

    def is_tradable(self, symbol: str) -> bool:
        provider = self._require_provider()
        if hasattr(provider, "is_tradable"):
            return bool(provider.is_tradable(symbol, today=self._today))
        return True

    def industry(self, symbol: str) -> str:
        provider = self._require_provider()
        if hasattr(provider, "industry"):
            return str(provider.industry(symbol))
        return ""

    def market_cap(self, symbol: str) -> float | None:
        provider = self._require_provider()
        if hasattr(provider, "market_cap"):
            v = provider.market_cap(symbol, today=self._today)
            return None if v is None else float(v)
        return None

    # ------------------------------------------------------------------
    # Runner-side mutators (NOT exposed to user code)
    # ------------------------------------------------------------------
    def _attach(
        self,
        data_provider: Any,
        broker: Any,
        cash: float,
    ) -> None:
        object.__setattr__(self, "_data_provider", data_provider)
        object.__setattr__(self, "_broker", broker)
        object.__setattr__(self, "cash", float(cash))
        object.__setattr__(self, "_equity", float(cash))

    def _set_today(self, ts: pd.Timestamp) -> None:
        object.__setattr__(self, "_today", ts)

    def _drain_orders(self) -> list[OrderIntent]:
        out = list(self._orders)
        self._orders.clear()
        return out

    def _drain_risk_rules(self) -> list[RiskRule]:
        out = list(self._risk_rules)
        self._risk_rules.clear()
        return out

    def _set_position(self, pos: Position) -> None:
        if pos.qty <= 0:
            self._positions.pop(pos.symbol, None)
        else:
            self._positions[pos.symbol] = pos

    def _update_cash_equity(self, cash: float, equity: float) -> None:
        object.__setattr__(self, "cash", float(cash))
        object.__setattr__(self, "_equity", float(equity))

    # ------------------------------------------------------------------
    def to_config_dict(self) -> dict[str, Any]:
        """Serializable snapshot of setup() — used for reproducibility hash."""
        return {k: getattr(self, k) for k in sorted(self._CONFIG_KEYS)}
