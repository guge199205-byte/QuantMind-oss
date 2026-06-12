"""Backtest loop — drives Context through setup → on_universe → on_bar.

Pulled out of worker.py so it can be unit-tested with InMemoryProvider.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Callable

import pandas as pd

from ..runner.progress import Phase, ProgressPublisher
from ..runner.result_collector import EquityPoint, Metrics, RunResult
from ..sdk.bar import Bar
from ..sdk.context import Context
from .broker import SimpleBroker

logger = logging.getLogger(__name__)


def _build_calendar(provider: Any, start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """Pull trading dates between [start, end] from the data provider.

    The provider is expected to expose either ``calendar(start, end)`` or
    a benchmark history we can scrape dates from. Fall back to business days.
    """
    if hasattr(provider, "calendar"):
        try:
            cal = provider.calendar(start, end)
            return [pd.Timestamp(d) for d in cal]
        except Exception:
            pass
    # In-memory provider path: scrape dates from any known DataFrame
    if hasattr(provider, "_data"):
        seen: set[pd.Timestamp] = set()
        for df in provider._data.values():  # type: ignore[attr-defined]
            for ts in df.index:
                t = pd.Timestamp(ts)
                if start <= t <= end:
                    seen.add(t)
        return sorted(seen)
    return list(pd.bdate_range(start, end))


def run_backtest(
    *,
    ctx: Context,
    provider: Any,
    user_globals: dict[str, Any],
    publisher: ProgressPublisher | None = None,
    progress_every: int = 5,
) -> RunResult:
    """Run setup → loop → aggregate. Returns a populated RunResult."""

    started_at = time.time()
    if publisher:
        publisher.publish(Phase.setup, 5.0, "running setup(ctx)")

    setup_fn = user_globals.get("setup")
    if not callable(setup_fn):
        raise RuntimeError("setup(ctx) is required")
    setup_fn(ctx)
    ctx.assert_ready()

    cash = float(ctx.cash) if ctx.cash is not None else 1_000_000.0
    broker = SimpleBroker(ctx=ctx, provider=provider, cash=cash)
    ctx._attach(data_provider=provider, broker=broker, cash=cash)

    on_bar = user_globals.get("on_bar")
    on_universe = user_globals.get("on_universe")
    on_finish = user_globals.get("on_finish")

    start = pd.Timestamp(ctx.start)
    end = pd.Timestamp(ctx.end)
    calendar = _build_calendar(provider, start, end)
    if not calendar:
        raise RuntimeError(
            f"No trading days in calendar between {start.date()} and {end.date()} — "
            "is the data provider populated?"
        )

    # Resolve universe to a concrete symbol list
    universe = ctx.universe
    if isinstance(universe, str):
        # Named pool — resolve via provider if it knows how, else InMemoryProvider keys
        if hasattr(provider, "resolve_universe"):
            symbols = list(provider.resolve_universe(universe))
        elif hasattr(provider, "_data"):
            symbols = sorted(provider._data.keys())  # type: ignore[attr-defined]
        else:
            symbols = []
    else:
        symbols = [str(s) for s in (universe or [])]

    if publisher:
        publisher.publish(
            Phase.load_data, 15.0,
            f"calendar={len(calendar)} days, universe={len(symbols)} symbols",
        )

    n_days = len(calendar)
    last_emit_pct = 15.0
    for i, today in enumerate(calendar):
        ctx._set_today(today)

        if on_universe is not None:
            try:
                snap = provider.snapshot(date=today, symbols=symbols)
            except Exception:
                snap = pd.DataFrame()
            try:
                on_universe(ctx, today, snap)
            except Exception as e:
                ctx.log(f"on_universe error @ {today.date()}: {e}", level="warning")

        if on_bar is not None:
            for sym in symbols:
                try:
                    df = provider.history(
                        symbol=sym, n=1,
                        fields=["open", "high", "low", "close", "volume"],
                        today=today,
                    )
                except Exception:
                    continue
                if df is None or len(df) == 0:
                    continue
                row = df.iloc[-1]
                try:
                    bar = Bar(
                        symbol=sym,
                        date=today,
                        open=float(row.get("open", 0.0) or 0.0),
                        high=float(row.get("high", 0.0) or 0.0),
                        low=float(row.get("low", 0.0) or 0.0),
                        close=float(row.get("close", 0.0) or 0.0),
                        volume=float(row.get("volume", 0.0) or 0.0),
                        adj_close=float(row.get("adj_close", row.get("close", 0.0)) or 0.0),
                    )
                except Exception:
                    continue
                try:
                    on_bar(ctx, bar)
                except Exception as e:
                    ctx.log(f"on_bar error {sym} @ {today.date()}: {e}", level="warning")

        orders = ctx._drain_orders()
        ctx._drain_risk_rules()  # Day-2: rules recorded but not enforced yet
        broker.process_day(today, orders)

        pct = 15.0 + (i + 1) * 75.0 / max(n_days, 1)
        if publisher and (pct - last_emit_pct) >= progress_every:
            publisher.publish(
                Phase.backtest, pct,
                f"day {i + 1}/{n_days} — equity={broker.equity:,.0f}",
            )
            last_emit_pct = pct

    if publisher:
        publisher.publish(Phase.aggregate, 92.0, "computing metrics")

    if on_finish is not None:
        try:
            on_finish(ctx)
        except Exception as e:
            ctx.log(f"on_finish error: {e}", level="warning")

    eq = broker.equity_curve
    trades = broker.trades
    metrics = _compute_metrics(eq, trades, initial_cash=cash)

    finished_at = time.time()
    result = RunResult(
        run_id="",  # filled in by worker
        status="success",
        metrics=metrics,
        equity=eq,
        trades=trades,
        positions=broker.positions_snapshot(calendar[-1]) if calendar else [],
        config=ctx.to_config_dict(),
        elapsed_sec=round(finished_at - started_at, 3),
        started_at=started_at,
        finished_at=finished_at,
    )
    return result


def _compute_metrics(
    equity: list[EquityPoint],
    trades: list,
    initial_cash: float,
) -> Metrics:
    if not equity or initial_cash <= 0:
        return Metrics()

    values = [p.value for p in equity]
    cum_return = (values[-1] - initial_cash) / initial_cash

    days = len(values)
    annual_return = 0.0
    if days > 1 and values[-1] > 0:
        years = days / 252.0
        if years > 0:
            ratio = values[-1] / initial_cash
            if ratio > 0:
                annual_return = ratio ** (1.0 / years) - 1.0

    rets: list[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev > 0:
            rets.append((values[i] - prev) / prev)

    sharpe = 0.0
    if len(rets) > 1:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        if std > 1e-12:
            sharpe = mean / std * math.sqrt(252.0)

    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd

    sells = [t for t in trades if t.direction == "SELL" and t.pnl is not None]
    win_rate = 0.0
    if sells:
        wins = sum(1 for t in sells if (t.pnl or 0) > 0)
        win_rate = wins / len(sells)

    avg_position = 0.0
    if values:
        invested = [v for v in values if v > 0]
        if invested:
            avg_position = sum(invested) / len(invested) / initial_cash

    return Metrics(
        cum_return=round(cum_return, 6),
        annual_return=round(annual_return, 6),
        sharpe=round(sharpe, 4),
        max_drawdown=round(max_dd, 6),
        win_rate=round(win_rate, 4),
        n_trades=len(trades),
        avg_position=round(avg_position, 4),
    )
