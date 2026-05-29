"""
数据源模块
"""

from typing import Dict, Optional, Tuple
from collections.abc import Iterable

import pandas as pd


class DataFeed:
    """数据源类，支持单标的或多标的行情"""

    def __init__(self):
        """初始化数据源"""
        self.market_data: dict[str, pd.DataFrame] = {}
        self.symbols = set()

    def _validate_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证并标准化单个标的数据框"""
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"数据缺少必要列: {missing_columns}")

        frame = df.copy()
        if not isinstance(frame.index, pd.DatetimeIndex):
            if "date" in frame.columns:
                frame.set_index("date", inplace=True)
            else:
                frame.index = pd.to_datetime(frame.index)
        frame.sort_index(inplace=True)
        return frame

    def set_data(self, data) -> None:
        """
        设置数据，支持两种形式：
        1. DataFrame（视为单标的），列包含 open/high/low/close/volume
        2. Dict[symbol, DataFrame]，每个 DataFrame 结构同上
        3. DataFrame 包含 'symbol' 列，会自动拆分为多标的
        """
        self.market_data.clear()
        self.symbols.clear()

        if isinstance(data, dict):
            for symbol, df in data.items():
                frame = self._validate_frame(df)
                self.market_data[symbol] = frame
                self.symbols.add(symbol)
        elif isinstance(data, pd.DataFrame):
            if "symbol" in data.columns:
                for symbol, df in data.groupby("symbol"):
                    frame = self._validate_frame(df.drop(columns=["symbol"]))
                    self.market_data[symbol] = frame
                    self.symbols.add(symbol)
            else:
                frame = self._validate_frame(data)
                self.market_data["DEFAULT"] = frame
                self.symbols.add("DEFAULT")
        else:
            raise TypeError("data 必须是 DataFrame 或 Dict[str, DataFrame]")

    def get_data(self) -> dict[str, pd.DataFrame]:
        """获取全部行情数据，返回 symbol -> DataFrame"""
        if not self.market_data:
            raise ValueError("未设置数据")
        return self.market_data

    def get_dates(self) -> Iterable[pd.Timestamp]:
        """获取所有日期（按时间排序，去重）"""
        if not self.market_data:
            return []
        all_dates = set()
        for df in self.market_data.values():
            all_dates.update(df.index.tolist())
        return sorted(all_dates)

    def get_market_data(self, date) -> dict[str, pd.Series]:
        """获取指定日期的多标的行情切片"""
        snapshot: dict[str, pd.Series] = {}
        for symbol, df in self.market_data.items():
            if date in df.index:
                snapshot[symbol] = df.loc[date]
        return snapshot

    def get_date_range(self) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """获取数据日期范围（全市场最小/最大日期）"""
        if not self.market_data:
            return None, None
        starts = [df.index.min() for df in self.market_data.values()]
        ends = [df.index.max() for df in self.market_data.values()]
        return min(starts), max(ends)

    def get_symbol_list(self) -> list:
        """获取标的列表"""
        return list(self.symbols) if self.symbols else []
