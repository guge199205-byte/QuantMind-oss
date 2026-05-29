"""加密货币市场适配器 (Binance)"""

from __future__ import annotations

import os
from pathlib import Path

from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter


# CryptoAlpha 因子集 — 加密货币专用 (90+ 因子)
# 来源: RD-Agent-C (wietrade/RD-Agent-C)
CRYPTO_ALPHA = {
    # K线形态 (无 $vwap，用 CPOS 替代)
    "CKMID": "($close-$open)/$open",
    "CKLEN": "($high-$low)/$open",
    "CKMID2": "($close-$open)/($high-$low+1e-12)",
    "CKUP": "($high-Greater($open, $close))/$open",
    "CKUP2": "($high-Greater($open, $close))/($high-$low+1e-12)",
    "CKLOW": "(Less($open, $close)-$low)/$open",
    "CKLOW2": "(Less($open, $close)-$low)/($high-$low+1e-12)",
    "CKSFT": "(2*$close-$high-$low)/$open",
    "CKSFT2": "(2*$close-$high-$low)/($high-$low+1e-12)",
    "COPEN0": "$open/$close",
    "CHIGH0": "$high/$close",
    "CLOW0": "$low/$close",
    "CPOS": "(2*$close-$high-$low)/($high-$low+1e-12)",
    # 短期动量 (3-21天)
    "CROC3": "Ref($close, 3)/$close",
    "CROC5": "Ref($close, 5)/$close",
    "CROC10": "Ref($close, 10)/$close",
    "CROC15": "Ref($close, 15)/$close",
    "CROC21": "Ref($close, 21)/$close",
    # 对数收益动量
    "CLRET3": "Log($close/Ref($close, 3))",
    "CLRET5": "Log($close/Ref($close, 5))",
    "CLRET10": "Log($close/Ref($close, 10))",
    "CLRET21": "Log($close/Ref($close, 21))",
    # 均线
    "CMA3": "Mean($close, 3)/$close",
    "CMA5": "Mean($close, 5)/$close",
    "CMA10": "Mean($close, 10)/$close",
    "CMA15": "Mean($close, 15)/$close",
    "CMA21": "Mean($close, 21)/$close",
    # 波动率
    "CSTD3": "Std($close, 3)/$close",
    "CSTD5": "Std($close, 5)/$close",
    "CSTD10": "Std($close, 10)/$close",
    "CSTD15": "Std($close, 15)/$close",
    "CSTD21": "Std($close, 21)/$close",
    "CLSTD5": "Std(Log($close/Ref($close,1)), 5)",
    "CLSTD10": "Std(Log($close/Ref($close,1)), 10)",
    "CLSTD21": "Std(Log($close/Ref($close,1)), 21)",
    # 趋势强度
    "CRSQR5": "Rsquare($close, 5)",
    "CRSQR10": "Rsquare($close, 10)",
    "CRSQR15": "Rsquare($close, 15)",
    "CRSQR21": "Rsquare($close, 21)",
    # 价格极值
    "CMAX5": "Max($high, 5)/$close",
    "CMAX10": "Max($high, 10)/$close",
    "CMAX15": "Max($high, 15)/$close",
    "CMAX21": "Max($high, 21)/$close",
    "CMIN5": "Min($low, 5)/$close",
    "CMIN10": "Min($low, 10)/$close",
    "CMIN15": "Min($low, 15)/$close",
    "CMIN21": "Min($low, 21)/$close",
    # RSV
    "CRSV5": "($close-Min($low, 5))/(Max($high, 5)-Min($low, 5)+1e-12)",
    "CRSV10": "($close-Min($low, 10))/(Max($high, 10)-Min($low, 10)+1e-12)",
    "CRSV21": "($close-Min($low, 21))/(Max($high, 21)-Min($low, 21)+1e-12)",
    # 量价相关 (Log-Log)
    "CCORR5": "Corr(Log($close), Log($volume+1), 5)",
    "CCORR10": "Corr(Log($close), Log($volume+1), 10)",
    "CCORR21": "Corr(Log($close), Log($volume+1), 21)",
    "CCORD5": "Corr(Log($close/Ref($close,1)), Log($volume/Ref($volume,1)+1), 5)",
    "CCORD10": "Corr(Log($close/Ref($close,1)), Log($volume/Ref($volume,1)+1), 10)",
    "CCORD21": "Corr(Log($close/Ref($close,1)), Log($volume/Ref($volume,1)+1), 21)",
    # 成交量 (Log scale)
    "CVMA5": "Log(Mean($volume, 5))/(Log($volume)+1e-12)",
    "CVMA10": "Log(Mean($volume, 10))/(Log($volume)+1e-12)",
    "CVMA21": "Log(Mean($volume, 21))/(Log($volume)+1e-12)",
    "CVSTD5": "Std(Log($volume), 5)",
    "CVSTD10": "Std(Log($volume), 10)",
    "CVSTD21": "Std(Log($volume), 21)",
    "CVOLCH5": "Log($volume/Ref($volume,5))",
    "CVOLCH10": "Log($volume/Ref($volume,10))",
    "CVOLCH21": "Log($volume/Ref($volume,21))",
    # 涨跌天数
    "CCNTP5": "Mean($close>Ref($close, 1), 5)",
    "CCNTP10": "Mean($close>Ref($close, 1), 10)",
    "CCNTP21": "Mean($close>Ref($close, 1), 21)",
    "CCNTD5": "Mean($close>Ref($close, 1), 5)-Mean($close<Ref($close, 1), 5)",
    "CCNTD10": "Mean($close>Ref($close, 1), 10)-Mean($close<Ref($close, 1), 10)",
    "CCNTD21": "Mean($close>Ref($close, 1), 21)-Mean($close<Ref($close, 1), 21)",
    # 量价交互
    "CPVVOL5": "Corr($close, $volume, 5)",
    "CPVVOL10": "Corr($close, $volume, 10)",
    "CPVVOL21": "Corr($close, $volume, 21)",
}


@register_adapter
class CryptoAdapter(MarketAdapter):
    """加密货币 (Binance) 市场适配器"""

    market_id = "crypto"
    market_name = "加密货币"
    description = "Binance 加密货币合约 (7×24)，CryptoAlpha 因子集 (90+ 因子)"

    def get_data_config(self) -> DataConfig:
        return DataConfig(
            provider_uri=self.get_qlib_provider_uri(),
            data_dir="/app/db/crypto_data",
            calendar="day",
            market="all",
            extra={"symbols": "BTCUSDT,ETHUSDT,..."},
        )

    def get_qlib_provider_uri(self) -> str:
        container_path = "/app/db/qlib_data/crypto_data"
        if os.path.isdir(container_path):
            return container_path
        host_path = os.path.join(
            os.getenv("PROJECT_ROOT", "/opt/quantmind"),
            "db", "qlib_data", "crypto_data",
        )
        return host_path

    def get_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            annualization_days=365,
            limit_threshold=1.0,  # 无涨跌停
            commission_rate=0.001,
            min_commission=0.0,  # 按比例收费
            region="cn",  # Qlib region 仍用 cn（数据格式相同）
            needs_adjustment_factor=False,  # 加密货币无复权
            extra={"crypto_mode": True},
        )

    def get_factor_set(self) -> dict[str, str]:
        return CRYPTO_ALPHA.copy()

    def get_factor_set_name(self) -> str:
        return "crypto_alpha"

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
            "CRYPTO_MODE": "true",
        }

    def prepare_data(self) -> bool:
        """下载并转换加密货币数据"""
        from ..data_pipeline.crypto_data import (
            convert_h5_to_qlib_format,
            download_all_crypto,
        )

        try:
            h5_path = download_all_crypto()
            convert_h5_to_qlib_format(h5_path)
            return True
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error("Crypto data preparation failed: %s", e)
            return False

    def is_data_ready(self) -> bool:
        provider = self.get_qlib_provider_uri()
        return os.path.isdir(provider) and os.path.isfile(os.path.join(provider, "calendars", "day.txt"))
