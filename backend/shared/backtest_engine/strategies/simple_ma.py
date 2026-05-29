"""
简单移动平均策略示例
"""

from typing import Any, Dict

import numpy as np

from .base import BaseStrategy


class SimpleMAStrategy(BaseStrategy):
    """
    简单移动平均策略

    当短期均线上穿长期均线时买入，下穿时卖出
    """

    def __init__(self, short_window: int = 5, long_window: int = 20, **kwargs):
        """
        初始化策略

        Args:
            short_window: 短期均线窗口
            long_window: 长期均线窗口
        """
        super().__init__("SimpleMA", **kwargs)
        self.short_window = short_window
        self.long_window = long_window

        # 数据存储
        self.price_history = []
        self.short_ma = None
        self.long_ma = None
        self.position = 0  # 0: 空仓, 1: 满仓

    def on_data(self, market_data: dict[str, Any]) -> None:
        """
        数据更新时调用

        Args:
            market_data: 市场数据字典
        """
        current_price = market_data["close"]
        self.price_history.append(current_price)

        # 需要足够的数据才能计算均线
        if len(self.price_history) < self.long_window:
            return

        # 计算移动平均
        prices = np.array(self.price_history)
        self.short_ma = np.mean(prices[-self.short_window :])
        self.long_ma = np.mean(prices[-self.long_window :])

        # 获取当前持仓
        current_position = 0
        if hasattr(self, "backtest_engine") and self.backtest_engine:
            positions = self.backtest_engine.portfolio.get_positions()
            current_position = sum(pos["quantity"] for pos in positions.values())

        # 交易逻辑
        if self.short_ma > self.long_ma and current_position == 0:
            # 买入信号
            cash = self.get_cash()
            quantity = int(cash / current_price * 0.95)  # 使用95%的资金
            if quantity > 0:
                self.buy("STOCK", quantity)
                self.position = 1

        elif self.short_ma < self.long_ma and current_position > 0:
            # 卖出信号
            self.sell("STOCK", current_position)
            self.position = 0

    def on_order_filled(self, order: dict[str, Any]) -> None:
        """
        订单成交时调用

        Args:
            order: 订单信息
        """
        action = "买入" if order["side"] == "buy" else "卖出"
        print(f"{action}订单成交: {order['quantity']}股 @ {order['price']:.2f}")
