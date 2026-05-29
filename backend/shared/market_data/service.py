"""
统一市场数据服务
提供股票数据获取、处理和管理功能
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..unified_config import get_config

logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    """市场数据结构"""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None


@dataclass
class StockInfo:
    """股票信息"""

    symbol: str
    name: str
    exchange: str
    industry: str | None = None
    market_cap: float | None = None


class MarketDataService:
    """统一市场数据服务"""

    def __init__(self):
        self.config = get_config()
        self._cache = {}

    async def get_market_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> dict[str, Any]:
        """
        获取市场数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期

        Returns:
            Dict: 市场数据
        """
        if not symbols:
            raise ValueError("股票代码列表不能为空")

        try:
            # 验证时间范围
            if start_date >= end_date:
                raise ValueError("开始日期必须早于结束日期")

            # 限制数据量
            days_diff = (end_date - start_date).days
            if days_diff > 365 * 5:  # 最多5年数据
                logger.warning(f"数据范围过大，限制为5年: {days_diff}天 -> 1825天")
                end_date = start_date + timedelta(days=365 * 5)

            result = {
                "symbols": symbols,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timeframe": timeframe,
                "data": {},
                "errors": [],
            }

            # 从数据库获取数据
            for symbol in symbols:
                try:
                    stock_data = await self._get_stock_data_from_db(symbol, start_date, end_date)
                    result["data"][symbol] = stock_data
                    logger.info(f"成功获取股票 {symbol} 数据: {len(stock_data)} 条记录")
                except Exception as e:
                    error_msg = f"获取股票 {symbol} 数据失败: {e}"
                    logger.warning(error_msg)
                    result["data"][symbol] = []
                    result["errors"].append(error_msg)

            # 如果所有股票都获取失败，抛出异常
            if all(len(data) == 0 for data in result["data"].values()):
                raise ValueError("所有股票数据获取失败")

            return result

        except ValueError as e:
            logger.error(f"获取市场数据参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            raise RuntimeError(f"市场数据获取失败: {e}")

    async def _get_stock_data_from_db(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """从数据库获取股票数据"""
        try:
            # 提取股票代码（去掉交易所后缀）
            symbol.split(".")[0] if "." in symbol else symbol

            # 使用直接数据库连接查询股票数据

            # 这里需要根据实际的数据库表结构来查询
            # 暂时返回模拟数据
            dates = []
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:  # 只包含工作日
                    dates.append(current_date)
                current_date += timedelta(days=1)

            # 生成模拟数据
            import random

            base_price = 10.0 + random.random() * 90  # 10-100元基础价格

            data = []
            for date in dates:
                price_change = random.uniform(-0.05, 0.05)  # ±5%日内波动
                open_price = base_price * (1 + random.uniform(-0.02, 0.02))
                close_price = open_price * (1 + price_change)
                high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.03))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.03))
                # 100万-5000万成交量
                volume = int(random.uniform(1000000, 50000000))

                data.append(
                    {
                        "date": date.isoformat(),
                        "open": round(open_price, 2),
                        "high": round(high_price, 2),
                        "low": round(low_price, 2),
                        "close": round(close_price, 2),
                        "volume": volume,
                        "adj_close": round(close_price, 2),
                    }
                )

                # 更新基础价格为当日收盘价
                base_price = close_price

            return data

        except Exception as e:
            logger.error(f"从数据库获取股票 {symbol} 数据失败: {e}")
            raise

    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """获取股票信息"""
        if not symbol or not symbol.strip():
            logger.warning("股票代码不能为空")
            return None

        try:
            code = symbol.split(".")[0] if "." in symbol else symbol

            # 验证股票代码格式
            if not code.isdigit() or len(code) != 6:
                logger.warning(f"无效的股票代码格式: {symbol}")
                return None

            # 使用直接数据库连接查询股票信息
            # 这里需要根据实际的数据库表结构来查询
            # 暂时返回模拟数据
            stock_info = StockInfo(
                symbol=symbol,
                name=f"股票{code}",
                exchange=("深交所" if code.startswith("0") or code.startswith("3") else "上交所"),
                industry="金融",
                market_cap=1000000000,  # 10亿
            )

            logger.info(f"成功获取股票 {symbol} 信息")
            return stock_info

        except Exception as e:
            logger.error(f"获取股票 {symbol} 信息失败: {e}")
            return None

    async def search_stocks(self, keyword: str, limit: int = 10) -> list[StockInfo]:
        """搜索股票"""
        if not keyword or not keyword.strip():
            logger.warning("搜索关键词不能为空")
            return []

        if limit <= 0 or limit > 100:
            logger.warning(f"搜索限制数量无效: {limit}，使用默认值10")
            limit = 10

        try:
            # 使用直接数据库连接搜索股票
            # 这里需要根据实际的数据库表结构来查询
            # 暂时返回模拟数据
            results = []

            # 模拟搜索结果
            if keyword.isdigit() and len(keyword) == 6:
                # 按代码搜索
                stock_info = StockInfo(
                    symbol=keyword,
                    name=f"股票{keyword}",
                    exchange="深交所" if keyword.startswith("0") else "上交所",
                    industry="金融",
                )
                results.append(stock_info)
                logger.info(f"按代码搜索找到股票: {keyword}")
            else:
                # 按名称搜索
                for i in range(min(limit, 5)):
                    code = f"{100000 + i:06d}"
                    stock_info = StockInfo(
                        symbol=code,
                        name=f"{keyword}股票{i + 1}",
                        exchange="深交所" if i % 2 == 0 else "上交所",
                        industry="金融",
                    )
                    results.append(stock_info)
                logger.info(f"按名称搜索找到 {len(results)} 只股票")

            return results

        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
            return []

    async def get_stock_pool(self, pool_name: str = "default") -> list[str]:
        """获取股票池"""
        if not pool_name or not pool_name.strip():
            pool_name = "default"

        try:
            # 这里可以从数据库或配置文件中获取股票池
            # 暂时返回默认股票池
            default_pools = {
                "default": ["000001.SZ", "600000.SH", "000858.SZ", "600519.SH"],
                "large_cap": ["000001.SZ", "600036.SH", "600519.SH", "000858.SZ"],
                "tech": ["000858.SZ", "300059.SZ", "002415.SZ", "300750.SZ"],
                "finance": ["000001.SZ", "600000.SH", "600036.SH", "000858.SZ"],
            }

            stock_pool = default_pools.get(pool_name, default_pools["default"])
            logger.info(f"获取股票池 {pool_name}: {len(stock_pool)} 只股票")
            return stock_pool

        except Exception as e:
            logger.error(f"获取股票池失败: {e}")
            # 返回最小默认股票池
            fallback_pool = ["000001.SZ", "600000.SH"]
            logger.warning(f"使用备用股票池: {fallback_pool}")
            return fallback_pool


# 全局实例
_market_data_service = None


def get_market_data_service() -> MarketDataService:
    """获取市场数据服务实例"""
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service


# 便捷函数
async def get_market_data(
    symbols: list[str], start_date: datetime, end_date: datetime, timeframe: str = "1d"
) -> dict[str, Any]:
    """获取市场数据便捷函数"""
    service = get_market_data_service()
    return await service.get_market_data(symbols, start_date, end_date, timeframe)


async def get_stock_info(symbol: str) -> StockInfo | None:
    """获取股票信息便捷函数"""
    service = get_market_data_service()
    return await service.get_stock_info(symbol)


async def search_stocks(keyword: str, limit: int = 10) -> list[StockInfo]:
    """搜索股票便捷函数"""
    service = get_market_data_service()
    return await service.search_stocks(keyword, limit)


async def get_stock_pool(pool_name: str = "default") -> list[str]:
    """获取股票池便捷函数"""
    service = get_market_data_service()
    return await service.get_stock_pool(pool_name)
