"""MarketAdapter 基类 — 封装市场特定的数据、配置、因子集"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BacktestConfig:
    """回测参数配置"""
    # 年化天数
    annualization_days: int = 252
    # 涨跌停限制 (1.0 = 无限制)
    limit_threshold: float = 0.1
    # 佣金费率
    commission_rate: float = 0.001
    # 最低佣金 (元)
    min_commission: float = 5.0
    # Qlib region
    region: str = "cn"
    # 是否需要复权因子
    needs_adjustment_factor: bool = True
    # 额外参数
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataConfig:
    """数据管线配置"""
    # Qlib provider URI
    provider_uri: str = ""
    # 数据目录
    data_dir: str = ""
    # 交易日历
    calendar: str = "day"
    # 市场名称 (Qlib instruments)
    market: str = "csi300"
    # 额外参数
    extra: dict[str, Any] = field(default_factory=dict)


class MarketAdapter(ABC):
    """市场适配器基类

    每个市场实现一个子类，封装：
    - 数据管线配置
    - 回测参数
    - 因子集
    - RD-Agent PropSetting
    """

    # 子类必须定义
    market_id: str = ""
    market_name: str = ""
    description: str = ""

    # ── 数据配置 ──

    @abstractmethod
    def get_data_config(self) -> DataConfig:
        """获取数据管线配置"""

    @abstractmethod
    def get_qlib_provider_uri(self) -> str:
        """获取 Qlib 数据目录"""

    # ── 回测参数 ──

    @abstractmethod
    def get_backtest_config(self) -> BacktestConfig:
        """获取回测参数"""

    # ── 因子集 ──

    @abstractmethod
    def get_factor_set(self) -> dict[str, str]:
        """获取默认因子集 (name -> expression)"""

    def get_factor_set_name(self) -> str:
        """获取因子集名称"""
        return f"{self.market_id}_factors"

    # ── RD-Agent 配置 ──

    @abstractmethod
    def get_prop_setting_class(self) -> str:
        """获取 RD-Agent PropSetting 类的完整路径"""

    @abstractmethod
    def get_env_overrides(self) -> dict[str, str]:
        """获取需要传递给子进程的环境变量"""

    # ── 数据准备 ──

    def prepare_data(self) -> bool:
        """准备市场数据（下载、转换等）。返回是否成功。"""
        return True

    def is_data_ready(self) -> bool:
        """检查数据是否已准备好"""
        config = self.get_data_config()
        import os
        return os.path.isdir(config.provider_uri)
