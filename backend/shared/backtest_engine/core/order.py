"""
订单管理模块
"""

from datetime import datetime
from enum import Enum
from typing import Optional


class OrderType(Enum):
    """订单类型"""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(Enum):
    """订单方向"""

    BUY = "buy"
    SELL = "sell"
    SHORT_SELL = "short_sell"    # 融券开空
    BUY_TO_COVER = "buy_to_cover"  # 买入平空


class OrderStatus(Enum):
    """订单状态"""

    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Order:
    """订单类"""

    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
        order_id: str | None = None,
    ):
        """
        初始化订单

        Args:
            symbol: 交易标的
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格（限价单必需）
            order_id: 订单ID
        """
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.order_id = order_id or f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 执行相关
        self.status = OrderStatus.PENDING
        self.filled_quantity = 0.0
        self.filled_price: float | None = None
        self.created_at = datetime.now()
        self.filled_at: datetime | None = None
        self.reject_reason: str | None = None

    def __repr__(self) -> str:
        return (
            f"Order(id={self.order_id}, symbol={self.symbol}, side={self.side.value}, "
            f"type={self.order_type.value}, quantity={self.quantity}, price={self.price}, "
            f"status={self.status.value})"
        )
