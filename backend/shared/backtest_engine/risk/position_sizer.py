"""
仓位管理器
提供多种仓位计算和分配策略
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PositionSizingConfig:
    """仓位管理配置"""

    method: str = "fixed"  # 仓位计算方法
    base_position_size: float = 0.1  # 基础仓位比例
    max_position_size: float = 0.2  # 最大仓位比例
    min_position_size: float = 0.01  # 最小仓位比例
    max_positions: int = 10  # 最大持仓数量
    rebalance_threshold: float = 0.05  # 再平衡阈值
    volatility_lookback: int = 20  # 波动率回看期
    risk_adjustment_factor: float = 1.0  # 风险调整因子


class PositionSizerBase(ABC):
    """仓位计算器基类"""

    def __init__(self, config: PositionSizingConfig):
        self.config = config

    @abstractmethod
    def calculate_position_size(self, **kwargs) -> float:
        """计算仓位大小"""

    def validate_position_size(self, size: float, portfolio_value: float) -> float:
        """验证并调整仓位大小"""
        if portfolio_value <= 0:
            return 0.0

        position_value = size
        position_ratio = position_value / portfolio_value

        # 应用最大最小限制
        position_ratio = max(
            self.config.min_position_size,
            min(position_ratio, self.config.max_position_size),
        )

        return portfolio_value * position_ratio


class FixedPositionSizer(PositionSizerBase):
    """固定仓位计算器"""

    def calculate_position_size(self, portfolio_value: float, **kwargs) -> float:
        """计算固定仓位大小"""
        position_value = portfolio_value * self.config.base_position_size
        return self.validate_position_size(position_value, portfolio_value)


class PercentPositionSizer(PositionSizerBase):
    """百分比仓位计算器"""

    def __init__(self, config: PositionSizingConfig):
        super().__init__(config)
        self.confidence_levels = {
            "low": 0.05,
            "medium": 0.1,
            "high": 0.15,
            "very_high": 0.2,
        }

    def calculate_position_size(self, portfolio_value: float, confidence: str = "medium", **kwargs) -> float:
        """根据信心水平计算仓位大小"""
        base_ratio = self.confidence_levels.get(confidence, self.config.base_position_size)
        position_value = portfolio_value * base_ratio
        return self.validate_position_size(position_value, portfolio_value)


class VolatilityPositionSizer(PositionSizerBase):
    """波动率调整仓位计算器"""

    def calculate_position_size(
        self,
        portfolio_value: float,
        symbol: str,
        returns: list[float],
        current_price: float,
        target_volatility: float = 0.15,
        **kwargs,
    ) -> float:
        """基于波动率计算仓位大小"""
        if len(returns) < self.config.volatility_lookback:
            logger.warning(f"{symbol} 历史数据不足，使用默认仓位")
            return portfolio_value * self.config.base_position_size

        # 计算历史波动率
        recent_returns = returns[-self.config.volatility_lookback :]
        volatility = np.std(recent_returns) * np.sqrt(252)  # 年化波动率

        # 根据波动率调整仓位
        if volatility > 0:
            position_ratio = (target_volatility / volatility) * self.config.base_position_size
        else:
            position_ratio = self.config.base_position_size

        # 应用风险调整因子
        position_ratio *= self.config.risk_adjustment_factor

        position_value = portfolio_value * position_ratio
        return self.validate_position_size(position_value, portfolio_value)


class KellyPositionSizer(PositionSizerBase):
    """Kelly公式仓位计算器"""

    def calculate_position_size(
        self,
        portfolio_value: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        **kwargs,
    ) -> float:
        """使用Kelly公式计算仓位大小"""
        if avg_loss == 0 or win_rate == 0:
            return 0.0

        # Kelly公式: f = (bp - q) / b
        # 其中: b = 平均盈利/平均亏损, p = 胜率, q = 1-p
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p

        if b <= 0:
            return 0.0

        kelly_fraction = (b * p - q) / b

        # 保守处理：使用Kelly公式的一半
        kelly_fraction *= 0.5

        # 确保不会出现负数或过大的仓位
        kelly_fraction = max(0, min(kelly_fraction, self.config.max_position_size))

        position_value = portfolio_value * kelly_fraction
        return self.validate_position_size(position_value, portfolio_value)


class RiskParityPositionSizer(PositionSizerBase):
    """风险平价仓位计算器"""

    def __init__(self, config: PositionSizingConfig):
        super().__init__(config)
        self.target_risk_contribution = 1.0 / config.max_positions

    def calculate_position_size(
        self,
        portfolio_value: float,
        symbol: str,
        all_returns: dict[str, list[float]],
        all_volatilities: dict[str, float],
        **kwargs,
    ) -> float:
        """基于风险平价计算仓位大小"""
        if symbol not in all_returns or symbol not in all_volatilities:
            return portfolio_value * self.config.base_position_size

        symbol_volatility = all_volatilities[symbol]
        if symbol_volatility == 0:
            return 0.0

        # 风险平价权重计算
        inv_volatility = 1.0 / symbol_volatility
        total_inv_volatility = sum(1.0 / vol for vol in all_volatilities.values() if vol > 0)

        if total_inv_volatility > 0:
            risk_parity_weight = inv_volatility / total_inv_volatility
        else:
            risk_parity_weight = 1.0 / len(all_volatilities)

        position_value = portfolio_value * risk_parity_weight
        return self.validate_position_size(position_value, portfolio_value)


class AdaptivePositionSizer(PositionSizerBase):
    """自适应仓位计算器"""

    def __init__(self, config: PositionSizingConfig):
        super().__init__(config)
        self.performance_history = []
        self.max_history = 20

    def calculate_position_size(
        self,
        portfolio_value: float,
        recent_performance: float,
        market_volatility: float,
        **kwargs,
    ) -> float:
        """基于近期表现和市场条件自适应计算仓位"""
        # 记录近期表现
        self.performance_history.append(recent_performance)
        if len(self.performance_history) > self.max_history:
            self.performance_history.pop(0)

        # 基础仓位
        base_position = self.config.base_position_size

        # 表现调整
        if len(self.performance_history) >= 5:
            recent_avg = np.mean(self.performance_history[-5:])
            if recent_avg > 0.02:  # 近期表现好
                performance_multiplier = 1.2
            elif recent_avg < -0.02:  # 近期表现差
                performance_multiplier = 0.8
            else:
                performance_multiplier = 1.0
        else:
            performance_multiplier = 1.0

        # 市场波动率调整
        if market_volatility > 0.25:  # 高波动
            volatility_multiplier = 0.7
        elif market_volatility < 0.10:  # 低波动
            volatility_multiplier = 1.3
        else:
            volatility_multiplier = 1.0

        # 综合调整
        adjusted_position = base_position * performance_multiplier * volatility_multiplier

        position_value = portfolio_value * adjusted_position
        return self.validate_position_size(position_value, portfolio_value)


class PositionSizer:
    """仓位管理器主类"""

    def __init__(self, config: PositionSizingConfig | None = None):
        self.config = config or PositionSizingConfig()
        self._sizers = {
            "fixed": FixedPositionSizer(self.config),
            "percent": PercentPositionSizer(self.config),
            "volatility": VolatilityPositionSizer(self.config),
            "kelly": KellyPositionSizer(self.config),
            "risk_parity": RiskParityPositionSizer(self.config),
            "adaptive": AdaptivePositionSizer(self.config),
        }

    def calculate_position_size(self, method: str, **kwargs) -> float:
        """
        计算仓位大小

        Args:
            method: 仓位计算方法
            **kwargs: 方法特定参数

        Returns:
            建议的仓位价值
        """
        if method not in self._sizers:
            logger.error(f"不支持的仓位计算方法: {method}")
            return 0.0

        try:
            return self._sizers[method].calculate_position_size(**kwargs)
        except Exception as e:
            logger.error(f"仓位计算失败: {e}")
            return 0.0

    def calculate_optimal_positions(
        self,
        portfolio_value: float,
        available_symbols: list[str],
        market_data: dict[str, dict],
        method: str = "volatility",
    ) -> dict[str, float]:
        """
        计算最优仓位分配

        Args:
            portfolio_value: 投资组合价值
            available_symbols: 可用股票列表
            market_data: 市场数据
            method: 仓位计算方法

        Returns:
            股票代码到仓位价值的映射
        """
        positions = {}

        if method == "equal_weight":
            # 等权重分配
            equal_weight = min(1.0 / len(available_symbols), self.config.max_position_size)
            for symbol in available_symbols:
                positions[symbol] = portfolio_value * equal_weight

        elif method == "volatility":
            # 基于波动率的分配
            volatilities = {}
            returns_dict = {}

            for symbol in available_symbols:
                if symbol in market_data and "returns" in market_data[symbol]:
                    returns = market_data[symbol]["returns"]
                    if len(returns) >= self.config.volatility_lookback:
                        recent_returns = returns[-self.config.volatility_lookback :]
                        volatility = np.std(recent_returns) * np.sqrt(252)
                        volatilities[symbol] = volatility
                        returns_dict[symbol] = returns

            if volatilities:
                # 使用风险平价计算器
                risk_parity_sizer = self._sizers["risk_parity"]
                for symbol in available_symbols:
                    if symbol in volatilities:
                        position_value = risk_parity_sizer.calculate_position_size(
                            portfolio_value=portfolio_value,
                            symbol=symbol,
                            all_returns=returns_dict,
                            all_volatilities=volatilities,
                        )
                        positions[symbol] = position_value

        else:
            # 使用其他方法为每个股票单独计算
            for symbol in available_symbols:
                if symbol in market_data:
                    symbol_data = market_data[symbol]
                    position_value = self.calculate_position_size(
                        method=method,
                        portfolio_value=portfolio_value,
                        symbol=symbol,
                        **symbol_data,
                    )
                    positions[symbol] = position_value

        # 确保总仓位不超过限制
        total_position_value = sum(positions.values())
        if total_position_value > portfolio_value * 0.95:  # 保留5%现金
            scale_factor = (portfolio_value * 0.95) / total_position_value
            for symbol in positions:
                positions[symbol] *= scale_factor

        return positions

    def should_rebalance(
        self, current_positions: dict[str, float], target_positions: dict[str, float]
    ) -> tuple[bool, dict[str, float]]:
        """
        判断是否需要再平衡

        Args:
            current_positions: 当前持仓
            target_positions: 目标持仓

        Returns:
            (是否需要再平衡, 需要调整的持仓)
        """
        rebalance_needed = False
        adjustments = {}

        total_portfolio_value = sum(current_positions.values())

        for symbol, target_value in target_positions.items():
            current_value = current_positions.get(symbol, 0)
            current_weight = current_value / total_portfolio_value if total_portfolio_value > 0 else 0
            target_weight = target_value / total_portfolio_value if total_portfolio_value > 0 else 0

            weight_diff = abs(current_weight - target_weight)

            if weight_diff > self.config.rebalance_threshold:
                rebalance_needed = True
                adjustments[symbol] = target_value - current_value

        # 对于不再持有的股票，如果当前有持仓则需要卖出
        for symbol, current_value in current_positions.items():
            if symbol not in target_positions and current_value > 0:
                rebalance_needed = True
                adjustments[symbol] = -current_value

        return rebalance_needed, adjustments

    def get_position_summary(self, positions: dict[str, float], portfolio_value: float) -> dict[str, any]:
        """
        获取仓位摘要信息

        Args:
            positions: 持仓字典
            portfolio_value: 投资组合价值

        Returns:
            仓位摘要
        """
        if not positions:
            return {
                "total_positions": 0,
                "total_position_value": 0,
                "cash_ratio": 1.0,
                "position_count": 0,
                "positions": {},
            }

        total_position_value = sum(positions.values())
        cash_ratio = (portfolio_value - total_position_value) / portfolio_value if portfolio_value > 0 else 1.0

        position_details = {}
        for symbol, value in positions.items():
            weight = value / portfolio_value if portfolio_value > 0 else 0
            position_details[symbol] = {
                "value": value,
                "weight": weight,
                "weight_pct": weight * 100,
            }

        return {
            "total_positions": len(positions),
            "total_position_value": total_position_value,
            "cash_ratio": cash_ratio,
            "cash_ratio_pct": cash_ratio * 100,
            "position_count": len([v for v in positions.values() if v > 0]),
            "positions": position_details,
        }
