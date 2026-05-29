"""
Data Adapter - Converts real-time market data to Qlib-compatible format.

核心改进: 集成 HistoryBuffer，基于历史滑动窗口计算真实技术指标，
而非单点数据硬编码常数值。
"""

import logging
from typing import Any

import pandas as pd

from .history_buffer import HistoryBuffer
from backend.shared.stock_utils import StockCodeUtil

logger = logging.getLogger(__name__)


class DataAdapter:
    """Adapts real-time market data to Qlib model input format."""

    def __init__(self, history_buffer: HistoryBuffer = None):
        # Standard field mapping from QuantMind to Qlib
        self.field_mapping = {
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "volume",
            "amount": "factor",
        }
        self.history = history_buffer or HistoryBuffer()

    def convert_realtime_data(self, data: dict[str, Any]) -> pd.DataFrame:
        """
        Convert real-time tick/bar data to Qlib format with technical indicators.

        流程:
          1. 标准化字段名
          2. 将当前 bar 追加到 HistoryBuffer
          3. 基于历史窗口计算真实 MA/volatility/returns
          4. 返回带完整技术指标的 DataFrame

        Args:
            data: Dictionary or list of dicts containing market data

        Returns:
            DataFrame in Qlib format with proper column names and indicators
        """
        try:
            # Create DataFrame from input data
            if isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            # Rename columns according to mapping
            df = df.rename(columns=self.field_mapping)

            # Ensure timestamp is datetime
            if "timestamp" in df.columns:
                df["datetime"] = pd.to_datetime(df["timestamp"])

            if "symbol" in df.columns:
                df["instrument"] = df["symbol"].apply(StockCodeUtil.to_prefix)
            elif "instrument" in df.columns:
                df["instrument"] = df["instrument"].apply(StockCodeUtil.to_prefix)

            # Process each row: append to history buffer and compute indicators
            for idx in range(len(df)):
                row = df.iloc[idx]
                symbol = StockCodeUtil.to_prefix(row.get("instrument") or row.get("symbol", "unknown"))

                # Build bar dict for history buffer
                bar = {}
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in row.index:
                        bar[col] = float(row[col]) if pd.notna(row[col]) else 0.0
                if "datetime" in row.index:
                    bar["datetime"] = str(row["datetime"])

                # Append to sliding window
                self.history.append(str(symbol), bar)

                # Compute real indicators from history window
                indicators = self.history.compute_indicators(str(symbol))

                # Write indicators back to DataFrame
                for key, value in indicators.items():
                    df.at[idx, key] = value

            return df

        except Exception as e:
            logger.error(f"Failed to convert data: {e}")
            raise

    def prepare_features(self, df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        """
        Prepare feature DataFrame for model prediction.

        Args:
            df: Input DataFrame with market data
            feature_columns: List of feature column names required by model

        Returns:
            DataFrame with only the required feature columns
        """
        try:
            # Select only required columns, fill missing with defaults
            [c for c in feature_columns if c in df.columns]
            missing = [c for c in feature_columns if c not in df.columns]

            if missing:
                logger.warning(f"Missing feature columns (filled with 0): {missing}")

            features = df.reindex(columns=feature_columns, fill_value=0).copy()

            # Handle NaN: forward fill → backward fill → zero
            features = features.ffill().bfill().fillna(0)

            return features

        except Exception as e:
            logger.error(f"Failed to prepare features: {e}")
            raise

    def validate_data(self, df: pd.DataFrame, required_fields: list[str]) -> bool:
        """
        Validate that input data contains all required fields.

        Args:
            df: Input DataFrame
            required_fields: List of required field names

        Returns:
            True if all required fields are present
        """
        missing_fields = set(required_fields) - set(df.columns)
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return False
        return True

    def get_buffer_stats(self) -> dict[str, Any]:
        """返回历史缓冲区统计信息"""
        return self.history.stats()
