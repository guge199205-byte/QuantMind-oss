"""美股市场适配器"""

from __future__ import annotations

import os

from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter


# 美股专用因子集 — 适配美股特性（无涨跌停、T+1、美元计价）
US_ALPHA = {
    # K线形态
    "USMID": "($close - $open) / $open",
    "USLEN": "($high - $low) / $open",
    "USMID2": "($close - $open) / ($high - $low + 1e-12)",
    "USUP": "($high - Greater($open, $close)) / $open",
    "USLOW": "(Less($open, $close) - $low) / $open",
    "USSFT": "(2 * $close - $high - $low) / $open",
    # 中期动量 (美股机构主导，趋势性强)
    "USROC5": "Ref($close, 5) / $close - 1",
    "USROC10": "Ref($close, 10) / $close - 1",
    "USROC20": "Ref($close, 20) / $close - 1",
    "USROC60": "Ref($close, 60) / $close - 1",
    # 均线
    "USMA5": "Mean($close, 5) / $close",
    "USMA10": "Mean($close, 10) / $close",
    "USMA20": "Mean($close, 20) / $close",
    "USMA60": "Mean($close, 60) / $close",
    # 波动率
    "USSTD5": "Std($close, 5) / $close",
    "USSTD10": "Std($close, 10) / $close",
    "USSTD20": "Std($close, 20) / $close",
    "USSTD60": "Std($close, 60) / $close",
    # 量价相关
    "USCORR5": "Corr(Log($close), Log($volume + 1), 5)",
    "USCORR10": "Corr(Log($close), Log($volume + 1), 10)",
    "USCORR20": "Corr(Log($close), Log($volume + 1), 20)",
    # 成交量变化
    "USVOLCH5": "Log($volume / Ref($volume, 5))",
    "USVOLCH10": "Log($volume / Ref($volume, 10))",
    "USVOLCH20": "Log($volume / Ref($volume, 20))",
    # RSV
    "USRSV5": "($close - Min($low, 5)) / (Max($high, 5) - Min($low, 5) + 1e-12)",
    "USRSV10": "($close - Min($low, 10)) / (Max($high, 10) - Min($low, 10) + 1e-12)",
    "USRSV20": "($close - Min($low, 20)) / (Max($high, 20) - Min($low, 20) + 1e-12)",
    # 趋势强度
    "USRSQR5": "Rsquare($close, 5)",
    "USRSQR10": "Rsquare($close, 10)",
    "USRSQR20": "Rsquare($close, 20)",
    # 价格极值
    "USMAX5": "Max($high, 5) / $close",
    "USMAX10": "Max($high, 10) / $close",
    "USMIN5": "Min($low, 5) / $close",
    "USMIN10": "Min($low, 10) / $close",
    # 涨跌天数
    "USCNTP5": "Mean($close > Ref($close, 1), 5)",
    "USCNTP10": "Mean($close > Ref($close, 1), 10)",
    "USCNTP20": "Mean($close > Ref($close, 1), 20)",
}


@register_adapter
class USStockAdapter(MarketAdapter):
    """美股市场适配器"""

    market_id = "us_stock"
    market_name = "美股"
    description = "美国股票市场 (S&P 500 + NASDAQ 100)，yfinance 数据源"

    def get_data_config(self) -> DataConfig:
        return DataConfig(
            provider_uri=self.get_qlib_provider_uri(),
            data_dir="/app/db/us_data",
            calendar="day",
            market="sp500",
        )

    def get_qlib_provider_uri(self) -> str:
        container_path = "/app/db/qlib_data/us_data"
        if os.path.isdir(container_path):
            return container_path
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
        return US_ALPHA.copy()

    def get_factor_set_name(self) -> str:
        return "us_alpha"

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
        """下载并转换美股数据"""
        from ..data_pipeline.us_data import (
            convert_h5_to_qlib_format,
            download_all_us,
        )

        try:
            h5_path = download_all_us()
            convert_h5_to_qlib_format(h5_path, self.get_qlib_provider_uri())
            return True
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error("US data preparation failed: %s", e)
            return False

    def is_data_ready(self) -> bool:
        from ..data_pipeline.us_data import is_us_data_ready
        return is_us_data_ready(self.get_qlib_provider_uri())
