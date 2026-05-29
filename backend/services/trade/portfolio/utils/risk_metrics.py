"""
风险指标计算模块

基于 PortfolioSnapshot 时间序列，计算：
- 夏普比率 (Sharpe Ratio)
- 波动率 (Volatility)
- 最大回撤 (Max Drawdown)
- 年化收益率 (Annualized Return)
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# 无风险利率（年化，默认使用中国十年期国债收益率约 2.5%）
DEFAULT_RISK_FREE_RATE = 0.025
TRADING_DAYS_PER_YEAR = 252


@dataclass
class RiskMetrics:
    """风险指标结果"""

    sharpe_ratio: float | None = None
    volatility: float | None = None
    annualized_volatility: float | None = None
    max_drawdown: float | None = None
    max_drawdown_start: str | None = None
    max_drawdown_end: str | None = None
    annualized_return: float | None = None
    calmar_ratio: float | None = None
    sortino_ratio: float | None = None


def calculate_daily_returns(values: list[float]) -> list[float]:
    """
    从净值序列计算日收益率

    Args:
        values: 每日净值序列 [v0, v1, v2, ...]

    Returns:
        日收益率序列 [r1, r2, ...], 长度 = len(values) - 1
    """
    if len(values) < 2:
        return []
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] != 0:
            r = (values[i] - values[i - 1]) / values[i - 1]
            returns.append(r)
        else:
            returns.append(0.0)
    return returns


def calculate_sharpe_ratio(
    daily_returns: list[float],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """
    计算夏普比率

    Sharpe = (Ra - Rf) / σa
    - Ra: 年化收益率
    - Rf: 无风险利率
    - σa: 年化波动率
    """
    if len(daily_returns) < 2:
        return None

    avg_daily = sum(daily_returns) / len(daily_returns)
    annualized_return = avg_daily * TRADING_DAYS_PER_YEAR

    volatility = _std(daily_returns)
    if volatility == 0:
        return None

    annualized_vol = volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (annualized_return - risk_free_rate) / annualized_vol
    return round(sharpe, 4)


def calculate_volatility(daily_returns: list[float]) -> float | None:
    """
    计算年化波动率

    σ_annual = σ_daily * √252
    """
    if len(daily_returns) < 2:
        return None
    vol = _std(daily_returns)
    annualized_vol = vol * math.sqrt(TRADING_DAYS_PER_YEAR)
    return round(annualized_vol, 4)


def calculate_max_drawdown(values: list[float]) -> float | None:
    """
    计算最大回撤

    MDD = max((peak - trough) / peak)
    """
    if len(values) < 2:
        return None

    peak = values[0]
    max_dd = 0.0

    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

    return round(max_dd, 4)


def calculate_sortino_ratio(
    daily_returns: list[float],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """
    计算索提诺比率（仅考虑下行风险）

    Sortino = (Ra - Rf) / σ_downside
    """
    if len(daily_returns) < 2:
        return None

    avg_daily = sum(daily_returns) / len(daily_returns)
    annualized_return = avg_daily * TRADING_DAYS_PER_YEAR

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    downside_returns = [min(r - daily_rf, 0) for r in daily_returns]
    downside_dev = math.sqrt(sum(r**2 for r in downside_returns) / len(downside_returns))

    if downside_dev == 0:
        return None

    annualized_downside = downside_dev * math.sqrt(TRADING_DAYS_PER_YEAR)
    sortino = (annualized_return - risk_free_rate) / annualized_downside
    return round(sortino, 4)


def calculate_calmar_ratio(daily_returns: list[float], values: list[float]) -> float | None:
    """
    计算卡玛比率

    Calmar = 年化收益率 / 最大回撤
    """
    if len(daily_returns) < 2 or len(values) < 2:
        return None

    avg_daily = sum(daily_returns) / len(daily_returns)
    annualized_return = avg_daily * TRADING_DAYS_PER_YEAR

    max_dd = calculate_max_drawdown(values)
    if not max_dd or max_dd == 0:
        return None

    return round(annualized_return / max_dd, 4)


def compute_risk_metrics(
    total_values: list[float],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> RiskMetrics:
    """
    一次性计算所有风险指标

    Args:
        total_values: 每日组合总市值序列
        risk_free_rate: 无风险利率（年化）

    Returns:
        RiskMetrics 数据对象
    """
    if len(total_values) < 2:
        return RiskMetrics()

    daily_returns = calculate_daily_returns(total_values)

    avg_daily = sum(daily_returns) / len(daily_returns)
    annualized_return = avg_daily * TRADING_DAYS_PER_YEAR

    return RiskMetrics(
        sharpe_ratio=calculate_sharpe_ratio(daily_returns, risk_free_rate),
        volatility=calculate_volatility(daily_returns),
        annualized_volatility=calculate_volatility(daily_returns),
        max_drawdown=calculate_max_drawdown(total_values),
        annualized_return=round(annualized_return, 4),
        calmar_ratio=calculate_calmar_ratio(daily_returns, total_values),
        sortino_ratio=calculate_sortino_ratio(daily_returns, risk_free_rate),
    )


def _std(data: list[float]) -> float:
    """计算标准差（样本标准差）"""
    n = len(data)
    if n < 2:
        return 0.0
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    return math.sqrt(variance)
