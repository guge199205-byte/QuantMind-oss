"""A股市场适配器"""

from __future__ import annotations

import os

from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter


@register_adapter
class AShareAdapter(MarketAdapter):
    """A股 (CSI300) 市场适配器"""

    market_id = "a_share"
    market_name = "A股"
    description = "中国 A 股市场 (CSI300)，Qlib Alpha158 因子集"

    def get_data_config(self) -> DataConfig:
        return DataConfig(
            provider_uri=self.get_qlib_provider_uri(),
            data_dir="/app/db/qlib_data/cn_data",
            calendar="day",
            market="csi300",
        )

    def get_qlib_provider_uri(self) -> str:
        # 容器内路径优先
        container_path = "/app/db/qlib_data/cn_data"
        if os.path.isdir(container_path):
            return container_path
        # 宿主机路径
        host_path = os.path.join(
            os.getenv("PROJECT_ROOT", "/opt/quantmind"),
            "db", "qlib_data", "cn_data",
        )
        return host_path

    def get_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            annualization_days=252,
            limit_threshold=0.1,
            commission_rate=0.001,
            min_commission=5.0,
            region="cn",
            needs_adjustment_factor=True,
        )

    def get_factor_set(self) -> dict[str, str]:
        """Alpha158 默认因子集 (ALPHA20 子集)"""
        return {
            "KMID": "($close - $open) / $open",
            "KLEN": "($high - $low) / $open",
            "KMID2": "($close - $open) / ($high - $low + 1e-12)",
            "KUP": "($high - Max($open, $close)) / $open",
            "KUP2": "($high - Max($open, $close)) / ($high - $low + 1e-12)",
            "KLOW": "(Min($open, $close) - $low) / $open",
            "KLOW2": "(Min($open, $close) - $low) / ($high - $low + 1e-12)",
            "KSFT": "(2 * $close - $high - $low) / $open",
            "KSFT2": "(2 * $close - $high - $low) / ($high - $low + 1e-12)",
            "ROC5": "Ref($close, 5) / $close - 1",
            "ROC10": "Ref($close, 10) / $close - 1",
            "ROC20": "Ref($close, 20) / $close - 1",
            "ROC30": "Ref($close, 30) / $close - 1",
            "ROC60": "Ref($close, 60) / $close - 1",
            "MA5": "Mean($close, 5) / $close",
            "MA10": "Mean($close, 10) / $close",
            "MA20": "Mean($close, 20) / $close",
            "MA30": "Mean($close, 30) / $close",
            "MA60": "Mean($close, 60) / $close",
            "STD5": "Std($close, 5) / $close",
            "STD10": "Std($close, 10) / $close",
            "STD20": "Std($close, 20) / $close",
            "STD30": "Std($close, 30) / $close",
            "STD60": "Std($close, 60) / $close",
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
            "CHAT_MAX_TOKENS": os.getenv("CHAT_MAX_TOKENS", "8000"),
            "CHAT_TEMPERATURE": os.getenv("CHAT_TEMPERATURE", "0.3"),
        }
