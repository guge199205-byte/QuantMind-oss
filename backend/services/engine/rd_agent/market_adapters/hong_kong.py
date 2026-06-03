"""港股市场适配器"""

from __future__ import annotations

import os

from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter


# 港股专用因子集 — 适配港股特性（无涨跌停、T+0、港币计价）
HK_ALPHA = {
    # K线形态
    "HKMID": "($close - $open) / $open",
    "HKLEN": "($high - $low) / $open",
    "HKMID2": "($close - $open) / ($high - $low + 1e-12)",
    "HKUP": "($high - Greater($open, $close)) / $open",
    "HKLOW": "(Less($open, $close) - $low) / $open",
    "HKSFT": "(2 * $close - $high - $low) / $open",
    # 短期动量 (港股 T+0，短线交易活跃)
    "HKROC3": "Ref($close, 3) / $close - 1",
    "HKROC5": "Ref($close, 5) / $close - 1",
    "HKROC10": "Ref($close, 10) / $close - 1",
    "HKROC20": "Ref($close, 20) / $close - 1",
    # 均线
    "HKMA5": "Mean($close, 5) / $close",
    "HKMA10": "Mean($close, 10) / $close",
    "HKMA20": "Mean($close, 20) / $close",
    # 波动率
    "HKSTD5": "Std($close, 5) / $close",
    "HKSTD10": "Std($close, 10) / $close",
    "HKSTD20": "Std($close, 20) / $close",
    # 量价相关
    "HKCORR5": "Corr(Log($close), Log($volume + 1), 5)",
    "HKCORR10": "Corr(Log($close), Log($volume + 1), 10)",
    # 成交量变化
    "HKVOLCH5": "Log($volume / Ref($volume, 5))",
    "HKVOLCH10": "Log($volume / Ref($volume, 10))",
    # RSV
    "HKRSV5": "($close - Min($low, 5)) / (Max($high, 5) - Min($low, 5) + 1e-12)",
    "HKRSV10": "($close - Min($low, 10)) / (Max($high, 10) - Min($low, 10) + 1e-12)",
    # 趋势强度
    "HKRSQR5": "Rsquare($close, 5)",
    "HKRSQR10": "Rsquare($close, 10)",
    # 价格极值
    "HKMAX5": "Max($high, 5) / $close",
    "HKMIN5": "Min($low, 5) / $close",
}


@register_adapter
class HongKongAdapter(MarketAdapter):
    """港股市场适配器"""

    market_id = "hong_kong"
    market_name = "港股"
    description = "香港股票市场 (恒生指数 + 恒生科技指数)，yfinance 数据源"

    def get_data_config(self) -> DataConfig:
        return DataConfig(
            provider_uri=self.get_qlib_provider_uri(),
            data_dir="/app/db/hk_data",
            calendar="day",
            market="hsi",
        )

    def get_qlib_provider_uri(self) -> str:
        container_path = "/app/db/qlib_data/hk_data"
        if os.path.isdir(container_path):
            return container_path
        return os.path.join(
            os.getenv("PROJECT_ROOT", "/opt/quantmind"),
            "db", "qlib_data", "hk_data",
        )

    def get_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            annualization_days=252,
            limit_threshold=1.0,  # 港股无涨跌停
            commission_rate=0.001,
            min_commission=50.0,  # 港股最低佣金 50 港币
            region="cn",
            needs_adjustment_factor=True,
        )

    def get_factor_set(self) -> dict[str, str]:
        return HK_ALPHA.copy()

    def get_factor_set_name(self) -> str:
        return "hk_alpha"

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

    def prepare_data(self) -> bool:
        """下载并转换港股数据"""
        from ..data_pipeline.hk_data import (
            convert_h5_to_qlib_format,
            download_all_hk,
        )

        try:
            h5_path = download_all_hk()
            convert_h5_to_qlib_format(h5_path, self.get_qlib_provider_uri())
            return True
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error("HK data preparation failed: %s", e)
            return False

    def is_data_ready(self) -> bool:
        from ..data_pipeline.hk_data import is_hk_data_ready
        return is_hk_data_ready(self.get_qlib_provider_uri())
