"""
策略基类
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    策略基类

    所有策略都应该继承此类并实现相应方法。
    """

    def __init__(self, name: str, **kwargs):
        """
        初始化策略

        Args:
            name: 策略名称
            **kwargs: 策略参数
        """
        self.name = name
        self.parameters = kwargs
        self.backtest_engine = None
        self.data = None

        logger.info(f"初始化策略: {name}")

    def set_backtest_engine(self, engine) -> None:
        """设置回测引擎引用"""
        self.backtest_engine = engine

    def set_data(self, data) -> None:
        """设置数据"""
        self.data = data

    @abstractmethod
    def on_data(self, market_data: dict[str, Any]) -> None:
        """
        数据更新时调用

        Args:
            market_data: 市场数据字典
        """

    @abstractmethod
    def on_order_filled(self, order: dict[str, Any]) -> None:
        """
        订单成交时调用

        Args:
            order: 订单信息
        """

    def buy(self, symbol: str, quantity: int, price: float | None = None, **kwargs) -> None:
        """买入"""
        if self.backtest_engine:
            from ..core.order import Order, OrderSide, OrderType

            order = Order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
                price=price or 0,
                **kwargs,
            )
            self.backtest_engine.place_order(order)

    def sell(self, symbol: str, quantity: int, price: float | None = None, **kwargs) -> None:
        """卖出"""
        if self.backtest_engine:
            from ..core.order import Order, OrderSide, OrderType

            order = Order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
                price=price or 0,
                **kwargs,
            )
            self.backtest_engine.place_order(order)

    def short_sell(self, symbol: str, quantity: int, price: float | None = None, **kwargs) -> None:
        """融券开空"""
        if self.backtest_engine:
            from ..core.order import Order, OrderSide, OrderType

            order = Order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.SHORT_SELL,
                order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
                price=price or 0,
                **kwargs,
            )
            self.backtest_engine.place_order(order)

    def buy_to_cover(self, symbol: str, quantity: int, price: float | None = None, **kwargs) -> None:
        """买入平空"""
        if self.backtest_engine:
            from ..core.order import Order, OrderSide, OrderType

            order = Order(
                symbol=symbol,
                quantity=quantity,
                side=OrderSide.BUY_TO_COVER,
                order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
                price=price or 0,
                **kwargs,
            )
            self.backtest_engine.place_order(order)

    def get_short_position(self, symbol: str) -> int:
        """获取空头持仓量（正数表示空头数量）"""
        if self.backtest_engine:
            qty = self.backtest_engine.portfolio.get_position(symbol)
            return abs(qty) if qty < 0 else 0
        return 0


        """获取持仓"""
        if self.backtest_engine:
            return self.backtest_engine.portfolio.get_position(symbol)
        return 0

    def get_cash(self) -> float:
        """获取现金"""
        if self.backtest_engine:
            return self.backtest_engine.portfolio.cash
        return 0.0

    def get_total_value(self) -> float:
        """获取总资产"""
        if self.backtest_engine:
            return self.backtest_engine.portfolio.get_total_value()
        return 0.0
