"""Minimal data provider used by Day-2 runner.

Wraps Qlib's ``D.features`` for OHLCV. Feature parquet support is added Day 4.

The provider is constructed inside the subprocess (so qlib.init() runs in
the sandbox). Tests inject a stub via the ``InMemoryProvider`` below.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_QLIB_DATA = "/app/db/qlib_data/cn_data"


# ---------------------------------------------------------------------------
# Symbol normalization — internal SHxxxxxx ↔ Qlib SH600036 ↔ user 600036.SH
# Qlib daily store uses lowercase prefix-form, e.g. "sh600036".
# ---------------------------------------------------------------------------
def to_qlib(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}{code}"
    if s[:2] in {"SH", "SZ", "BJ", "HK"}:
        return s.lower()
    if s.endswith("HK"):
        return s.lower()
    return s.lower()


def to_internal(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex}{code}"
    return s


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------
class InMemoryProvider:
    """Test provider — backed by an arbitrary OHLCV DataFrame."""

    def __init__(
        self,
        data: dict[str, pd.DataFrame],
        benchmark_series: pd.Series | None = None,
        feature_lookup: dict[tuple[str, pd.Timestamp], dict[str, float]] | None = None,
    ) -> None:
        self._data = data
        self._benchmark = benchmark_series
        self._features = feature_lookup or {}

    # ---- ctx.history ----
    def history(
        self,
        symbol: str | None = None,
        n: int = 20,
        field: str = "close",
        fields: Sequence[str] | None = None,
        symbols: Sequence[str] | None = None,
        today: pd.Timestamp | None = None,
    ) -> pd.Series | pd.DataFrame:
        if symbols:
            cols = {}
            for s in symbols:
                df = self._slice(s, today, n)
                cols[s] = df[field] if field in df.columns else pd.Series(dtype=float)
            return pd.DataFrame(cols)
        if symbol is None:
            return pd.Series(dtype=float)
        df = self._slice(symbol, today, n)
        if fields:
            return df[list(fields)]
        if field not in df.columns:
            return pd.Series(dtype=float)
        return df[field]

    def _slice(
        self, symbol: str, today: pd.Timestamp | None, n: int
    ) -> pd.DataFrame:
        df = self._data.get(symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        if today is not None:
            df = df.loc[: today]
        return df.tail(n)

    # ---- features ----
    def feature(
        self,
        symbol: str,
        name: str,
        n: int = 1,
        today: pd.Timestamp | None = None,
    ) -> float | pd.Series | None:
        df = self._data.get(symbol)
        if df is None or name not in df.columns:
            v = self._features.get((symbol, today))
            if v is not None and name in v:
                return float(v[name])
            return None
        if today is not None:
            df = df.loc[: today]
        if df.empty:
            return None
        if n == 1:
            return float(df[name].iloc[-1])
        return df[name].tail(n)

    def list_features(self) -> list[str]:
        seen: set[str] = set()
        for df in self._data.values():
            seen.update(df.columns)
        return sorted(seen - {"open", "high", "low", "close", "volume"})

    def snapshot(
        self,
        date: pd.Timestamp | None = None,
        symbols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        if date is None:
            return pd.DataFrame()
        rows = {}
        targets = symbols or list(self._data.keys())
        for s in targets:
            df = self._data.get(s)
            if df is None or df.empty:
                continue
            d = df.loc[:date]
            if d.empty:
                continue
            rows[s] = d.iloc[-1]
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).T

    def benchmark_history(
        self, symbol: str, n: int, today: pd.Timestamp | None
    ) -> pd.Series:
        if self._benchmark is None:
            return pd.Series(dtype=float)
        s = self._benchmark
        if today is not None:
            s = s.loc[:today]
        return s.tail(n)

    def is_st(self, symbol: str, today: pd.Timestamp | None = None) -> bool:
        return False

    def is_tradable(self, symbol: str, today: pd.Timestamp | None = None) -> bool:
        return True


# ---------------------------------------------------------------------------
# Qlib-backed provider (used by the actual runner subprocess)
# ---------------------------------------------------------------------------
class QlibProvider:
    """Lazy Qlib data provider — initialised on first call."""

    def __init__(
        self,
        data_path: str | None = None,
        region: str = "cn",
    ) -> None:
        self.data_path = data_path or os.getenv("QLIB_DATA_PATH", DEFAULT_QLIB_DATA)
        self.region = region
        self._initialised = False
        self._D: Any | None = None
        self._cache: dict[str, pd.DataFrame] = {}
        self._benchmark_cache: dict[str, pd.Series] = {}
        self._features_listed: list[str] | None = None

    def _ensure(self) -> Any:
        if self._initialised and self._D is not None:
            return self._D
        try:
            import qlib  # type: ignore
            from qlib.data import D  # type: ignore

            qlib.init(provider_uri=self.data_path, region=self.region)
            self._D = D
            self._initialised = True
            return D
        except Exception as e:
            raise RuntimeError(f"qlib.init failed at {self.data_path}: {e}") from e

    def _load(
        self, symbol: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        cache_key = f"{symbol}@{start}~{end}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        D = self._ensure()
        qsym = to_qlib(symbol)
        try:
            df = D.features(
                [qsym],
                ["$open", "$high", "$low", "$close", "$volume", "$factor"],
                start_time=start.strftime("%Y-%m-%d"),
                end_time=end.strftime("%Y-%m-%d"),
                freq="day",
            )
        except Exception as e:
            logger.debug("qlib load failed for %s: %s", symbol, e)
            self._cache[cache_key] = pd.DataFrame()
            return self._cache[cache_key]
        if df is None or df.empty:
            self._cache[cache_key] = pd.DataFrame()
            return self._cache[cache_key]
        df.columns = ["open", "high", "low", "close", "volume", "factor"]
        df = df.xs(qsym, level=0).sort_index()
        df["adj_close"] = df["close"]
        self._cache[cache_key] = df
        return df

    def history(
        self,
        symbol: str | None = None,
        n: int = 20,
        field: str = "close",
        fields: Sequence[str] | None = None,
        symbols: Sequence[str] | None = None,
        today: pd.Timestamp | None = None,
    ) -> pd.Series | pd.DataFrame:
        if today is None:
            today = pd.Timestamp.utcnow().normalize()
        start = today - pd.Timedelta(days=max(n * 2, 60))
        if symbols:
            cols = {}
            for s in symbols:
                df = self._load(s, start, today).tail(n)
                cols[s] = df[field] if field in df.columns else pd.Series(dtype=float)
            return pd.DataFrame(cols)
        if symbol is None:
            return pd.Series(dtype=float)
        df = self._load(symbol, start, today).tail(n)
        if fields:
            return df[list(fields)]
        if field not in df.columns:
            return pd.Series(dtype=float)
        return df[field]

    def feature(
        self,
        symbol: str,
        name: str,
        n: int = 1,
        today: pd.Timestamp | None = None,
    ) -> float | pd.Series | None:
        # Day 4 wires the parquet feature snapshot. Day 2 only knows OHLCV
        # mapped names ($close → close).
        df_field = name.lstrip("$")
        s = self.history(symbol=symbol, n=n, field=df_field, today=today)
        if isinstance(s, pd.Series) and not s.empty:
            return float(s.iloc[-1]) if n == 1 else s
        return None

    def list_features(self) -> list[str]:
        if self._features_listed is not None:
            return self._features_listed
        self._features_listed = ["open", "high", "low", "close", "volume", "adj_close"]
        return self._features_listed

    def snapshot(
        self,
        date: pd.Timestamp | None = None,
        symbols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        if not symbols or date is None:
            return pd.DataFrame()
        rows: dict[str, pd.Series] = {}
        for s in symbols:
            df = self._load(s, date - pd.Timedelta(days=10), date)
            if not df.empty:
                rows[s] = df.iloc[-1]
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).T

    def benchmark_history(
        self, symbol: str, n: int, today: pd.Timestamp | None
    ) -> pd.Series:
        if today is None:
            today = pd.Timestamp.utcnow().normalize()
        cache_key = f"bench:{symbol}:{n}:{today}"
        if cache_key in self._benchmark_cache:
            return self._benchmark_cache[cache_key]
        df = self._load(symbol, today - pd.Timedelta(days=max(n * 2, 60)), today).tail(n)
        s = df["close"] if "close" in df.columns else pd.Series(dtype=float)
        self._benchmark_cache[cache_key] = s
        return s

    def is_st(self, symbol: str, today: pd.Timestamp | None = None) -> bool:
        return False

    def is_tradable(self, symbol: str, today: pd.Timestamp | None = None) -> bool:
        return True


# ---------------------------------------------------------------------------
# Universe loader — read instruments/<pool>.txt
# ---------------------------------------------------------------------------
def load_universe(name: str, qlib_data_path: str | None = None) -> list[str]:
    """Read a Qlib instrument file and return prefix-form symbols."""
    qlib_data_path = qlib_data_path or os.getenv("QLIB_DATA_PATH", DEFAULT_QLIB_DATA)
    fp = Path(qlib_data_path) / "instruments" / f"{name}.txt"
    if not fp.exists():
        return []
    syms: set[str] = set()
    with fp.open() as f:
        for line in f:
            parts = line.strip().split("\t")
            if parts and parts[0]:
                syms.add(to_internal(parts[0]))
    return sorted(syms)


def data_snapshot_at(qlib_data_path: str | None = None) -> str | None:
    """Return last calendar date as YYYY-MM-DD (used for repro hash)."""
    qlib_data_path = qlib_data_path or os.getenv("QLIB_DATA_PATH", DEFAULT_QLIB_DATA)
    fp = Path(qlib_data_path) / "calendars" / "day.txt"
    if not fp.exists():
        return None
    try:
        with fp.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 256))
            tail = f.read().decode("utf-8", errors="ignore")
        last = [ln for ln in tail.strip().splitlines() if ln.strip()]
        return last[-1].strip() if last else None
    except Exception:
        return None
