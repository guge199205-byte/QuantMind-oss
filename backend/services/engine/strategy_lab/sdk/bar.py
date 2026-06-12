"""Bar — single-stock OHLCV snapshot passed to on_bar(ctx, bar)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Bar:
    """One trading day for one symbol.

    Spec: §4.2 (on_bar hook), §4.3.2 (data access).
    """

    symbol: str
    date: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float = 0.0
    _features: dict[str, float] = field(default_factory=dict, repr=False)

    def feature(self, name: str, default: float | None = None) -> float | None:
        """Return one of the 152-dim parquet features for this bar.

        Returns ``default`` (None) when the feature is absent or NaN.
        """
        val = self._features.get(name)
        if val is None:
            return default
        try:
            if pd.isna(val):
                return default
        except (TypeError, ValueError):
            pass
        return float(val)

    def has_feature(self, name: str) -> bool:
        return name in self._features

    @property
    def features(self) -> dict[str, float]:
        return dict(self._features)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat() if self.date is not None else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adj_close": self.adj_close,
        }
