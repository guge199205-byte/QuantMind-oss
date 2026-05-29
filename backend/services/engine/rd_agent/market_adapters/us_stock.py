"""美股市场适配器 (预留)"""

from __future__ import annotations

import os

from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter


@register_adapter
class USStockAdapter(MarketAdapter):
    """美股市场适配器 (待实现)"""

    market_id = "us_stock"
    market_name = "美股"
    description = "美国股票市场 (S&P 500)，待接入数据源"

    def get_data_config(self) -> DataConfig:
        return DataConfig(
            provider_uri=self.get_qlib_provider_uri(),
            data_dir="/app/db/us_data",
            calendar="day",
            market="sp500",
        )

    def get_qlib_provider_uri(self) -> str:
        return os.path.join(
            os.getenv("PROJECT_ROOT", "/opt/quantmind"),
            "db", "qlib_data", "us_data",
        )

    def get_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            annualization_days=252,
            limit_threshold=1.0,  # 美股无涨跌停
            commission_rate=0.001,
            min_commission=0.0,
            region="us",
            needs_adjustment_factor=True,
        )

    def get_factor_set(self) -> dict[str, str]:
        return {
            "KMID": "($close - $open) / $open",
            "KLEN": "($high - $low) / $open",
            "ROC5": "Ref($close, 5) / $close - 1",
            "ROC10": "Ref($close, 10) / $close - 1",
            "ROC20": "Ref($close, 20) / $close - 1",
            "MA5": "Mean($close, 5) / $close",
            "MA10": "Mean($close, 10) / $close",
            "MA20": "Mean($close, 20) / $close",
            "STD5": "Std($close, 5) / $close",
            "STD10": "Std($close, 10) / $close",
            "STD20": "Std($close, 20) / $close",
        }

    def get_prop_setting_class(self) -> str:
        return "rdagent.app.qlib_rd_loop.conf.FactorBasePropSetting"

    def get_env_overrides(self) -> dict[str, str]:
        return {
            "QLIB_PROVIDER_URI": self.get_qlib_provider_uri(),
            "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", ""),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "CHAT_MODEL": os.getenv("CHAT_MODEL", ""),
            "REASONING_MODEL": os.getenv("CHAT_MODEL", ""),
            "CHAT_STREAM": "false",
        }

    def is_data_ready(self) -> bool:
        return False  # 待实现
