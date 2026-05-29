from sqlalchemy import Boolean, Column, Index, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base, TimestampMixin


class Symbol(Base, TimestampMixin):
    """交易标的表 (收敛至 stocks 表)"""

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    stock_name = Column(String(200), nullable=False, comment="股票名称")
    exchange = Column(String(20), nullable=True, index=True, comment="交易所 (SH/SZ/HK/US)")
    market = Column(String(20), nullable=True, index=True, comment="市场类型 (A股/港股/美股)")
    sector = Column(String(200), comment="行业板块")
    status = Column(Integer, default=1, comment="状态：1-交易，0-暂停，-1-退市")

    # 兼容性别名
    @hybrid_property
    def symbol(self):
        return self.stock_code

    @symbol.setter
    def symbol(self, value):
        self.stock_code = value

    @hybrid_property
    def name(self):
        return self.stock_name

    @name.setter
    def name(self, value):
        self.stock_name = value

    @hybrid_property
    def is_active(self) -> bool:
        return self.status == 1

    @is_active.setter
    def is_active(self, value: bool):
        self.status = 1 if value else 0

    # 包含 stocks 表的其他字段以便映射正常
    industry = Column(String(200), nullable=True)
    market_cap = Column(String(200), nullable=True)  # 虽然 stocks 是 Float，模型层面定义匹配即可

    __table_args__ = (
        Index("idx_exchange", "exchange"),
        Index("idx_market", "market"),
        Index("idx_sector", "sector"),
    )
