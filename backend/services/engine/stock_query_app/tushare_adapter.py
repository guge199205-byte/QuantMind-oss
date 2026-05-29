"""
Tushare数据适配器占位符
用于智能选股服务的数据获取
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TushareAdapter:
    """Tushare数据适配器"""

    def __init__(self, token: str = None):
        """初始化Tushare适配器

        Args:
            token: Tushare API token
        """
        self.token = token
        self._available = False

    def is_available(self) -> bool:
        """检查适配器是否可用"""
        return self._available

    def get_stock_basic(self) -> list[dict[str, Any]]:
        """获取股票基本信息"""
        logger.warning("Tushare adapter not available, returning empty data")
        return []

    def get_daily_data(self, ts_code: str, start_date: str = None, end_date: str = None) -> list[dict[str, Any]]:
        """获取日线数据"""
        logger.warning("Tushare adapter not available, returning empty data")
        return []

    def get_stock_list(self) -> list[dict[str, Any]]:
        """获取股票列表"""
        logger.warning("Tushare adapter not available, returning empty data")
        return []


def get_tushare_adapter(token: str = None) -> TushareAdapter | None:
    """获取Tushare适配器实例

    Args:
        token: Tushare API token

    Returns:
        TushareAdapter实例，如果token为空则返回None
    """
    if not token:
        logger.warning("Tushare token not provided, adapter will be disabled")
        return None
    return TushareAdapter(token=token)
