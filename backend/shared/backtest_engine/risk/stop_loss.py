"""
止损止盈管理器
提供多种止损止盈策略
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StopLossConfig:
    """止损配置"""

    stop_loss_pct: float = 0.05  # 固定止损比例
    take_profit_pct: float = 0.15  # 固定止盈比例
    trailing_stop_pct: float = 0.03  # 移动止损比例
    max_loss_per_trade: float = 0.02  # 单笔最大亏损比例
    max_daily_loss: float = 0.05  # 单日最大亏损
    volatility_multiplier: float = 2.0  # 波动率倍数
    lookback_period: int = 20  # 回看期
    min_profit_for_trail: float = 0.02  # 启动移动止损的最小盈利


@dataclass
class Position:
    """持仓信息"""

    symbol: str
    side: str  # long/short
    entry_price: float
    quantity: int
    entry_time: datetime
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("in")
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_price: float = 0.0
    is_closed: bool = False
    close_time: datetime | None = None
    close_price: float | None = None
    close_reason: str | None = None


@dataclass
class StopLossOrder:
    """止损订单"""

    order_id: str
    position: Position
    stop_type: str  # fixed, trailing, atr, volatility
    trigger_price: float
    is_active: bool = True
    created_time: datetime = field(default_factory=datetime.now)
    triggered_time: datetime | None = None
    triggered_price: float | None = None


class StopLossStrategy(ABC):
    """止损策略基类"""

    def __init__(self, config: StopLossConfig):
        self.config = config

    @abstractmethod
    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """计算止损价格"""

    @abstractmethod
    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发止损"""

    def update_position(self, position: Position, current_price: float):
        """更新持仓信息"""
        position.current_price = current_price

        if position.side == "long":
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            position.highest_price = max(position.highest_price, current_price)
        else:  # short
            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
            position.lowest_price = min(position.lowest_price, current_price)


class FixedStopLoss(StopLossStrategy):
    """固定比例止损"""

    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """计算固定止损价格"""
        if position.side == "long":
            return position.entry_price * (1 - self.config.stop_loss_pct)
        else:  # short
            return position.entry_price * (1 + self.config.stop_loss_pct)

    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发固定止损"""
        self.update_position(position, current_price)

        if position.side == "long":
            if current_price <= position.stop_loss_price:
                return (
                    True,
                    f"触发固定止损: {current_price:.2f} <= {position.stop_loss_price:.2f}",
                )
        else:  # short
            if current_price >= position.stop_loss_price:
                return (
                    True,
                    f"触发固定止损: {current_price:.2f} >= {position.stop_loss_price:.2f}",
                )

        return False, ""


class TrailingStopLoss(StopLossStrategy):
    """移动止损"""

    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """计算移动止损价格"""
        if position.side == "long":
            # 初始止损价格
            initial_stop = position.entry_price * (1 - self.config.stop_loss_pct)

            # 如果已有盈利，设置移动止损
            if position.unrealized_pnl > 0:
                profit_pct = position.unrealized_pnl / (position.entry_price * position.quantity)
                if profit_pct >= self.config.min_profit_for_trail:
                    # 移动止损价格 = 当前价格 - 移动止损比例
                    trailing_stop = position.current_price * (1 - self.config.trailing_stop_pct)
                    return max(initial_stop, trailing_stop)

            return initial_stop
        else:  # short
            initial_stop = position.entry_price * (1 + self.config.stop_loss_pct)

            if position.unrealized_pnl > 0:
                profit_pct = position.unrealized_pnl / (position.entry_price * position.quantity)
                if profit_pct >= self.config.min_profit_for_trail:
                    trailing_stop = position.current_price * (1 + self.config.trailing_stop_pct)
                    return min(initial_stop, trailing_stop)

            return initial_stop

    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发移动止损"""
        self.update_position(position, current_price)

        # 更新移动止损价格
        new_stop_price = self.calculate_stop_loss_price(position)
        if new_stop_price != position.trailing_stop_price:
            position.trailing_stop_price = new_stop_price

        # 检查是否触发止损
        if position.side == "long":
            if current_price <= position.trailing_stop_price:
                return (
                    True,
                    f"触发移动止损: {current_price:.2f} <= {position.trailing_stop_price:.2f}",
                )
        else:  # short
            if current_price >= position.trailing_stop_price:
                return (
                    True,
                    f"触发移动止损: {current_price:.2f} >= {position.trailing_stop_price:.2f}",
                )

        return False, ""


class ATRStopLoss(StopLossStrategy):
    """基于ATR的止损"""

    def calculate_atr(
        self,
        prices: list[float],
        high_prices: list[float],
        low_prices: list[float],
        period: int = 14,
    ) -> float:
        """计算平均真实范围"""
        if len(prices) < period + 1:
            return 0.0

        tr_values = []
        for i in range(1, len(prices)):
            high_low = high_prices[i] - low_prices[i]
            high_close = abs(high_prices[i] - prices[i - 1])
            low_close = abs(low_prices[i] - prices[i - 1])
            tr = max(high_low, high_close, low_close)
            tr_values.append(tr)

        if len(tr_values) >= period:
            return np.mean(tr_values[-period:])
        return np.mean(tr_values) if tr_values else 0.0

    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """计算基于ATR的止损价格"""
        prices = kwargs.get("prices", [])
        high_prices = kwargs.get("high_prices", [])
        low_prices = kwargs.get("low_prices", [])

        if not prices or len(prices) < self.config.lookback_period:
            # 回退到固定止损
            return position.entry_price * (1 - self.config.stop_loss_pct)

        atr = self.calculate_atr(prices, high_prices, low_prices)
        if atr == 0:
            return position.entry_price * (1 - self.config.stop_loss_pct)

        atr_multiplier = kwargs.get("atr_multiplier", self.config.volatility_multiplier)

        if position.side == "long":
            return position.entry_price - (atr * atr_multiplier)
        else:  # short
            return position.entry_price + (atr * atr_multiplier)

    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发ATR止损"""
        self.update_position(position, current_price)

        if position.side == "long":
            if current_price <= position.stop_loss_price:
                return (
                    True,
                    f"触发ATR止损: {current_price:.2f} <= {position.stop_loss_price:.2f}",
                )
        else:  # short
            if current_price >= position.stop_loss_price:
                return (
                    True,
                    f"触发ATR止损: {current_price:.2f} >= {position.stop_loss_price:.2f}",
                )

        return False, ""


class VolatilityStopLoss(StopLossStrategy):
    """基于波动率的止损"""

    def calculate_volatility(self, returns: list[float], period: int = None) -> float:
        """计算波动率"""
        if period is None:
            period = self.config.lookback_period

        if len(returns) < period:
            return 0.0

        recent_returns = returns[-period:]
        return np.std(recent_returns)

    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """计算基于波动率的止损价格"""
        returns = kwargs.get("returns", [])

        if not returns or len(returns) < self.config.lookback_period:
            return position.entry_price * (1 - self.config.stop_loss_pct)

        volatility = self.calculate_volatility(returns)
        if volatility == 0:
            return position.entry_price * (1 - self.config.stop_loss_pct)

        # 使用波动率的倍数作为止损距离
        stop_distance = volatility * self.config.volatility_multiplier

        if position.side == "long":
            return position.entry_price * (1 - stop_distance)
        else:  # short
            return position.entry_price * (1 + stop_distance)

    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发波动率止损"""
        self.update_position(position, current_price)

        if position.side == "long":
            if current_price <= position.stop_loss_price:
                return (
                    True,
                    f"触发波动率止损: {current_price:.2f} <= {position.stop_loss_price:.2f}",
                )
        else:  # short
            if current_price >= position.stop_loss_price:
                return (
                    True,
                    f"触发波动率止损: {current_price:.2f} >= {position.stop_loss_price:.2f}",
                )

        return False, ""


class TimeBasedStopLoss(StopLossStrategy):
    """基于时间的止损"""

    def __init__(self, config: StopLossConfig, max_hold_time: timedelta = timedelta(days=30)):
        super().__init__(config)
        self.max_hold_time = max_hold_time

    def calculate_stop_loss_price(self, position: Position, **kwargs) -> float:
        """时间止损不直接计算价格，而是基于持仓时间"""
        return 0.0

    def should_trigger_stop(self, position: Position, current_price: float) -> tuple[bool, str]:
        """判断是否触发时间止损"""
        self.update_position(position, current_price)

        hold_time = datetime.now() - position.entry_time
        if hold_time >= self.max_hold_time:
            return (
                True,
                f"触发时间止损: 持仓时间 {hold_time.days} 天超过限制 {self.max_hold_time.days} 天",
            )

        return False, ""


class StopLossManager:
    """止损管理器"""

    def __init__(self, config: StopLossConfig | None = None):
        self.config = config or StopLossConfig()
        self.positions: dict[str, Position] = {}
        self.stop_orders: dict[str, StopLossOrder] = {}
        self.strategies = {
            "fixed": FixedStopLoss(self.config),
            "trailing": TrailingStopLoss(self.config),
            "atr": ATRStopLoss(self.config),
            "volatility": VolatilityStopLoss(self.config),
            "time": TimeBasedStopLoss(self.config),
        }

    def add_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: int,
        stop_loss_strategy: str = "fixed",
        **strategy_kwargs,
    ) -> str:
        """
        添加新持仓

        Args:
            symbol: 股票代码
            side: 持仓方向
            entry_price: 入场价格
            quantity: 数量
            stop_loss_strategy: 止损策略
            **strategy_kwargs: 策略参数

        Returns:
            持仓ID
        """
        position_id = f"{symbol}_{side}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(),
            highest_price=entry_price if side == "long" else 0,
            lowest_price=entry_price if side == "short" else float("in"),
        )

        # 计算初始止损价格
        if stop_loss_strategy in self.strategies:
            strategy = self.strategies[stop_loss_strategy]
            position.stop_loss_price = strategy.calculate_stop_loss_price(position, **strategy_kwargs)

        self.positions[position_id] = position

        # 创建止损订单
        stop_order = StopLossOrder(
            order_id=f"stop_{position_id}",
            position=position,
            stop_type=stop_loss_strategy,
            trigger_price=position.stop_loss_price,
        )
        self.stop_orders[position_id] = stop_order

        logger.info(f"添加持仓 {position_id}, 止损策略: {stop_loss_strategy}")
        return position_id

    def update_prices(self, price_updates: dict[str, float], **market_data):
        """
        更新价格并检查止损

        Args:
            price_updates: 价格更新字典
            **market_data: 市场数据
        """
        triggered_stops = []

        for position_id, position in self.positions.items():
            if position.is_closed:
                continue

            symbol = position.symbol
            if symbol not in price_updates:
                continue

            current_price = price_updates[symbol]
            strategy = self.strategies.get(self.stop_orders[position_id].stop_type)

            if strategy:
                should_stop, reason = strategy.should_trigger_stop(position, current_price)

                if should_stop:
                    triggered_stops.append((position_id, reason))

        return triggered_stops

    def close_position(self, position_id: str, close_price: float, close_reason: str):
        """平仓"""
        if position_id not in self.positions:
            return

        position = self.positions[position_id]
        position.is_closed = True
        position.close_time = datetime.now()
        position.close_price = close_price
        position.close_reason = close_reason

        # 计算已实现盈亏
        if position.side == "long":
            position.realized_pnl = (close_price - position.entry_price) * position.quantity
        else:  # short
            position.realized_pnl = (position.entry_price - close_price) * position.quantity

        # 停用止损订单
        if position_id in self.stop_orders:
            self.stop_orders[position_id].is_active = False

        logger.info(f"平仓 {position_id}, 价格: {close_price}, 原因: {close_reason}, 盈亏: {position.realized_pnl:.2f}")

    def update_stop_loss(self, position_id: str, new_stop_price: float):
        """手动更新止损价格"""
        if position_id in self.stop_orders:
            self.stop_orders[position_id].trigger_price = new_stop_price
            self.positions[position_id].stop_loss_price = new_stop_price
            logger.info(f"更新 {position_id} 止损价格至 {new_stop_price}")

    def get_position_summary(self, position_id: str) -> dict:
        """获取持仓摘要"""
        if position_id not in self.positions:
            return {}

        position = self.positions[position_id]
        stop_order = self.stop_orders.get(position_id)

        return {
            "position_id": position_id,
            "symbol": position.symbol,
            "side": position.side,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "quantity": position.quantity,
            "unrealized_pnl": position.unrealized_pnl,
            "realized_pnl": position.realized_pnl,
            "is_closed": position.is_closed,
            "entry_time": position.entry_time,
            "close_time": position.close_time,
            "close_reason": position.close_reason,
            "stop_loss_price": position.stop_loss_price,
            "stop_type": stop_order.stop_type if stop_order else None,
            "hold_days": (datetime.now() - position.entry_time).days,
        }

    def get_all_positions_summary(self) -> list[dict]:
        """获取所有持仓摘要"""
        return [self.get_position_summary(pid) for pid in self.positions.keys()]

    def get_risk_summary(self) -> dict:
        """获取风险摘要"""
        active_positions = [p for p in self.positions.values() if not p.is_closed]
        closed_positions = [p for p in self.positions.values() if p.is_closed]

        total_unrealized_pnl = sum(p.unrealized_pnl for p in active_positions)
        total_realized_pnl = sum(p.realized_pnl for p in closed_positions)

        winning_trades = [p for p in closed_positions if p.realized_pnl > 0]
        losing_trades = [p for p in closed_positions if p.realized_pnl < 0]

        win_rate = len(winning_trades) / len(closed_positions) if closed_positions else 0
        avg_win = np.mean([p.realized_pnl for p in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([p.realized_pnl for p in losing_trades]) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        return {
            "active_positions": len(active_positions),
            "closed_positions": len(closed_positions),
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "stop_orders_active": len([o for o in self.stop_orders.values() if o.is_active]),
        }

    def cleanup_closed_positions(self, older_than_days: int = 30):
        """清理旧的已平仓记录"""
        cutoff_time = datetime.now() - timedelta(days=older_than_days)

        to_remove = []
        for position_id, position in self.positions.items():
            if position.is_closed and position.close_time and position.close_time < cutoff_time:
                to_remove.append(position_id)

        for position_id in to_remove:
            del self.positions[position_id]
            if position_id in self.stop_orders:
                del self.stop_orders[position_id]

        logger.info(f"清理了 {len(to_remove)} 个旧持仓记录")

    def reset(self):
        """重置止损管理器"""
        self.positions.clear()
        self.stop_orders.clear()
        logger.info("止损管理器已重置")
