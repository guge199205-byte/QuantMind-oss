"""
History Buffer - Per-symbol sliding window for real-time technical indicator calculation.

解决核心问题: DataAdapter 单点推理时 MA/volatility/returns 全部为常数，
导致模型输入与训练数据分布不一致，预测结果无意义。

设计:
  - 每个 symbol 维护一个固定长度的环形缓冲区 (deque)
  - 新数据 append 后自动淘汰最旧数据
  - 提供 get_window() 返回含历史的 DataFrame，用于计算真实技术指标
"""

import logging
import threading
from collections import deque
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 默认窗口大小：至少能计算 MA20 + volatility_10
DEFAULT_WINDOW_SIZE = 30


class SymbolBuffer:
    """单个 symbol 的环形缓冲区"""

    __slots__ = ("symbol", "max_size", "_buffer")

    def __init__(self, symbol: str, max_size: int = DEFAULT_WINDOW_SIZE):
        self.symbol = symbol
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)

    def append(self, bar: dict[str, Any]):
        """追加一条 bar 数据"""
        self._buffer.append(bar)

    def size(self) -> int:
        return len(self._buffer)

    def to_dataframe(self) -> pd.DataFrame:
        """将缓冲区转为 DataFrame（时间正序）"""
        if not self._buffer:
            return pd.DataFrame()
        return pd.DataFrame(list(self._buffer))


class HistoryBuffer:
    """
    全局历史数据缓冲管理器。
    线程安全，支持多 symbol 并发写入。
    """

    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE):
        self.window_size = window_size
        self._buffers: dict[str, SymbolBuffer] = {}
        self._lock = threading.Lock()

    def append(self, symbol: str, bar: dict[str, Any]):
        """
        追加一条 bar 到指定 symbol 的缓冲区。

        Args:
            symbol: 证券代码
            bar: OHLCV bar 数据 (需包含 close, open, high, low, volume)
        """
        with self._lock:
            if symbol not in self._buffers:
                self._buffers[symbol] = SymbolBuffer(symbol, self.window_size)
            self._buffers[symbol].append(bar)

    def get_window(self, symbol: str) -> pd.DataFrame:
        """
        获取指定 symbol 的历史窗口 DataFrame。

        Returns:
            DataFrame，行按时间正序排列，包含缓冲区内所有历史 bar。
            如果无数据返回空 DataFrame。
        """
        with self._lock:
            buf = self._buffers.get(symbol)
            if buf is None:
                return pd.DataFrame()
            return buf.to_dataframe()

    def get_size(self, symbol: str) -> int:
        """获取指定 symbol 的缓冲区大小"""
        with self._lock:
            buf = self._buffers.get(symbol)
            return buf.size() if buf else 0

    def compute_indicators(self, symbol: str) -> dict[str, float]:
        """
        基于历史窗口计算真实技术指标。

        Returns:
            Dict 包含: ma5, ma10, ma20, returns, volatility_5, volatility_10,
                       high_low_ratio, close_open_ratio, volume_change, log_volume
        """
        df = self.get_window(symbol)
        n = len(df)

        if n == 0 or "close" not in df.columns:
            return self._default_indicators()

        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0.0] * n)

        result = {}

        # Moving Averages
        result["ma5"] = float(close.tail(min(5, n)).mean())
        result["ma10"] = float(close.tail(min(10, n)).mean())
        result["ma20"] = float(close.tail(min(20, n)).mean())

        # Returns (daily)
        if n >= 2:
            result["returns"] = (
                float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) if close.iloc[-2] != 0 else 0.0
            )
        else:
            result["returns"] = 0.0

        # Volatility (std of returns)
        if n >= 3:
            returns_series = close.pct_change().dropna()
            result["volatility_5"] = (
                float(returns_series.tail(min(5, len(returns_series))).std()) if len(returns_series) >= 2 else 0.01
            )
            result["volatility_10"] = (
                float(returns_series.tail(min(10, len(returns_series))).std()) if len(returns_series) >= 2 else 0.01
            )
        else:
            result["volatility_5"] = 0.01
            result["volatility_10"] = 0.01

        # High-Low ratio (latest bar)
        high_val = float(df["high"].iloc[-1]) if "high" in df.columns else float(close.iloc[-1])
        low_val = float(df["low"].iloc[-1]) if "low" in df.columns else float(close.iloc[-1])
        result["high_low_ratio"] = high_val / low_val if low_val != 0 else 1.0

        # Close-Open ratio (latest bar)
        open_val = float(df["open"].iloc[-1]) if "open" in df.columns else float(close.iloc[-1])
        result["close_open_ratio"] = float(close.iloc[-1]) / open_val if open_val != 0 else 1.0

        # Volume change
        if n >= 2 and "volume" in df.columns:
            prev_vol = float(volume.iloc[-2])
            curr_vol = float(volume.iloc[-1])
            result["volume_change"] = (curr_vol - prev_vol) / prev_vol if prev_vol != 0 else 0.0
        else:
            result["volume_change"] = 0.0

        # Log volume
        result["log_volume"] = float(np.log1p(volume.iloc[-1])) if n > 0 else 0.0

        return result

    @staticmethod
    def _default_indicators() -> dict[str, float]:
        """无历史数据时的默认指标值"""
        return {
            "ma5": 0.0,
            "ma10": 0.0,
            "ma20": 0.0,
            "returns": 0.0,
            "volatility_5": 0.01,
            "volatility_10": 0.01,
            "high_low_ratio": 1.0,
            "close_open_ratio": 1.0,
            "volume_change": 0.0,
            "log_volume": 0.0,
        }

    def clear(self, symbol: str | None = None):
        """清空缓冲区"""
        with self._lock:
            if symbol:
                self._buffers.pop(symbol, None)
            else:
                self._buffers.clear()

    def stats(self) -> dict[str, Any]:
        """缓冲区统计"""
        with self._lock:
            return {
                "symbols": len(self._buffers),
                "window_size": self.window_size,
                "details": {sym: buf.size() for sym, buf in self._buffers.items()},
            }
