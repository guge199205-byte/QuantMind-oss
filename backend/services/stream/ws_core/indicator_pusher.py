#!/usr/bin/env python3
"""
实时指标计算推送器
Week 20 Day 4
Updated: 2025-11-12 - 集成真实数据源
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from .indicators import BOLL, EMA, KDJ, MACD, RSI, TRIX
from .manager import manager

logger = logging.getLogger(__name__)

# 延迟导入避免循环依赖
_stock_repository = None
_market_data_repository = None


def get_stock_repository():
    """获取股票仓储实例"""
    global _stock_repository
    if _stock_repository is None:
        try:
            from backend.services.stream.container import Container

            container = Container.get_instance()
            _stock_repository = container.get_stock_repository()
        except Exception as e:
            logger.warning(f"无法获取StockRepository: {e}")
            _stock_repository = None
    return _stock_repository


def get_market_data_repository():
    """获取市场数据仓储实例"""
    global _market_data_repository
    if _market_data_repository is None:
        try:
            from backend.services.stream.container import Container

            container = Container.get_instance()
            _market_data_repository = container.get_market_data_repository()
        except Exception as e:
            logger.warning(f"无法获取MarketDataRepository: {e}")
            _market_data_repository = None
    return _market_data_repository


class IndicatorPusher:
    """实时指标推送器

    负责实时计算技术指标并推送到订阅的客户端
    """

    def __init__(self):
        """初始化推送器"""
        self.running = False
        self.push_tasks: dict[str, asyncio.Task] = {}
        self.push_interval = 2.0  # 推送间隔（秒）

        # 指标实例缓存
        self.indicators = {
            "MACD": MACD(),
            "RSI": RSI(),
            "BOLL": BOLL(),
            "TRIX": TRIX(),
            "KDJ": KDJ(),
            "EMA": EMA(),
        }

        # 数据缓存：{stock_code: DataFrame}
        self.data_cache: dict[str, pd.DataFrame] = {}

        logger.info("实时指标推送器初始化")

    async def start(self):
        """启动推送器"""
        self.running = True
        logger.info("实时指标推送器启动")

    async def stop(self):
        """停止推送器"""
        self.running = False

        # 取消所有推送任务
        for task in self.push_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.push_tasks.clear()
        logger.info("实时指标推送器停止")

    async def subscribe_indicator(self, stock_code: str, indicator_name: str):
        """
        订阅技术指标

        Args:
            stock_code: 股票代码
            indicator_name: 指标名称 (MACD, RSI, BOLL, TRIX等)
        """
        task_key = f"{stock_code}_{indicator_name}"

        if task_key in self.push_tasks:
            logger.debug(f"指标 {task_key} 已在推送列表中")
            return

        if indicator_name not in self.indicators:
            logger.warning(f"未知指标: {indicator_name}")
            return

            # 创建推送任务
        task = asyncio.create_task(self._push_indicator_loop(stock_code, indicator_name))
        self.push_tasks[task_key] = task
        logger.info(f"开始推送指标: {task_key}")

    async def unsubscribe_indicator(self, stock_code: str, indicator_name: str):
        """
        取消订阅技术指标

        Args:
            stock_code: 股票代码
            indicator_name: 指标名称
        """
        task_key = f"{stock_code}_{indicator_name}"

        if task_key in self.push_tasks:
            task = self.push_tasks[task_key]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.push_tasks[task_key]
            logger.info(f"停止推送指标: {task_key}")

    async def _push_indicator_loop(self, stock_code: str, indicator_name: str):
        """
        指标推送循环

        Args:
            stock_code: 股票代码
            indicator_name: 指标名称
        """
        topic = f"indicator.{stock_code}.{indicator_name}"

        while self.running:
            try:
                # 获取K线数据
                kline_data = await self._get_kline_data(stock_code)

                if kline_data is not None and not kline_data.empty:
                    # 计算指标
                    indicator = self.indicators[indicator_name]
                    result = indicator.calculate(kline_data)

                    # 推送到订阅者
                    message = {
                        "type": "indicator",
                        "stock_code": stock_code,
                        "indicator": indicator_name,
                        "data": result,
                        "timestamp": time.time(),
                    }

                    count = await manager.publish(topic, message)

                    if count > 0:
                        logger.debug(f"推送指标 {indicator_name} ({stock_code}) " f"到 {count} 个客户端")

                        # 等待下次推送
                await asyncio.sleep(self.push_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"推送指标错误 {stock_code} {indicator_name}: {e}")
                await asyncio.sleep(self.push_interval)

    async def _get_kline_data(self, stock_code: str, limit: int = 100) -> pd.DataFrame | None:
        """
        获取K线数据

        Args:
            stock_code: 股票代码
            limit: 数据条数

        Returns:
            K线数据DataFrame
        """
        # 检查缓存
        if stock_code in self.data_cache:
            df = self.data_cache[stock_code]

            # 增量更新：添加新的K线数据
            new_bar = await self._fetch_latest_bar(stock_code)
            if new_bar is not None:
                df = pd.concat([df, new_bar], ignore_index=True)
                # 保持最新100条
                if len(df) > limit:
                    df = df.tail(limit).reset_index(drop=True)
                self.data_cache[stock_code] = df

            return df

            # 首次获取完整数据
        df = await self._fetch_kline_data(stock_code, limit)
        if df is not None:
            self.data_cache[stock_code] = df

        return df

    async def _fetch_kline_data(self, stock_code: str, limit: int = 100) -> pd.DataFrame | None:
        """
        获取完整K线数据（混合模式：历史日线 + 当日实时分钟线）
        解决早盘指标空窗 Bug
        """
        import pandas as pd
        from sqlalchemy import text

        from backend.services.stream.market_app.database import AsyncSessionLocal

        # 计算回溯深度 (为保证指标稳定，回溯至少 30 个交易日)
        hist_depth = 30

        # SQL 1: 获取历史日线数据
        sql_hist = text("""
            SELECT 
                trade_date as date,
                open_price as open,
                high_price as high,
                low_price as low,
                close_price as close,
                volume_sum as volume
            FROM quote_daily_summaries
            WHERE symbol = :symbol
            ORDER BY trade_date DESC
            LIMIT :hist_limit
        """)

        # SQL 2: 聚合当日实时分钟线 (quotes 表)
        sql_today = text("""
            SELECT 
                date_trunc('minute', timestamp) as minute_ts,
                (array_agg(current_price ORDER BY timestamp ASC))[1] as open,
                MAX(current_price) as high,
                MIN(current_price) as low,
                (array_agg(current_price ORDER BY timestamp DESC))[1] as close,
                SUM(volume) as volume
            FROM quotes
            WHERE symbol = :symbol
            GROUP BY minute_ts
            ORDER BY minute_ts ASC
        """)

        try:
            async with AsyncSessionLocal() as session:
                # 并发执行两个查询
                hist_task = session.execute(sql_hist, {"symbol": stock_code, "hist_limit": hist_depth})
                today_task = session.execute(sql_today, {"symbol": stock_code})

                hist_res, today_res = await asyncio.gather(hist_task, today_task)

                hist_rows = hist_res.fetchall()
                today_rows = today_res.fetchall()

                # 1. 处理历史数据
                if hist_rows:
                    df_hist = pd.DataFrame(hist_rows, columns=["date", "open", "high", "low", "close", "volume"])
                    # 将 trade_date (date 对象) 转换为 datetime 以便拼接
                    df_hist["date"] = pd.to_datetime(df_hist["date"])
                    df_hist = df_hist.sort_values("date")
                else:
                    df_hist = pd.DataFrame()

                # 2. 处理当日数据
                if today_rows:
                    df_today = pd.DataFrame(today_rows, columns=["date", "open", "high", "low", "close", "volume"])
                else:
                    df_today = pd.DataFrame()

                # 3. 混合拼接
                if df_hist.empty and df_today.empty:
                    logger.debug(f"无任何历史或当日数据，使用模拟: {stock_code}")
                    return self._fetch_mock_kline_data(stock_code, limit)

                df_final = pd.concat([df_hist, df_today], ignore_index=True)

                # 限制返回给前端的条数，但保留计算指标所需的深度
                # 指标计算会在 get_indicators 中使用此 DataFrame 的全量
                return df_final.tail(limit + hist_depth).reset_index(drop=True)

        except Exception as e:
            logger.warning(f"获取混合 K 线失败 {stock_code}: {e}", exc_info=True)
            return self._fetch_mock_kline_data(stock_code, limit)

    def _fetch_mock_kline_data(self, stock_code: str, limit: int = 100) -> pd.DataFrame:
        """保持原有的模拟逻辑作为最后的安全回退"""
        import numpy as np

        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="1min")
        base_price = 100.0
        prices = []
        for i in range(limit):
            change = np.random.randn() * 0.5
            price = base_price + change
            prices.append(price)
            base_price = price
        df = pd.DataFrame(
            {
                "date": dates,
                "open": [p * 0.99 for p in prices],
                "high": [p * 1.01 for p in prices],
                "low": [p * 0.98 for p in prices],
                "close": prices,
                "volume": np.random.randint(1000, 10000, limit),
            }
        )
        return df

    async def _fetch_latest_bar(self, stock_code: str) -> pd.DataFrame | None:
        """
        获取最新一根K线

        Args:
            stock_code: 股票代码

        Returns:
            最新K线数据
        """
        # 尝试从真实数据源获取实时行情
        repo = get_stock_repository()
        if repo:
            try:
                data = await repo.get_realtime_data([stock_code])
                if data and stock_code in data:
                    quote = data[stock_code]
                    # 将实时行情转换为K线格式
                    new_bar = pd.DataFrame(
                        {
                            "date": [pd.Timestamp.now()],
                            "open": [float(quote.get("open", 100))],
                            "high": [float(quote.get("high", 101))],
                            "low": [float(quote.get("low", 99))],
                            "close": [float(quote.get("price", 100))],
                            "volume": [int(quote.get("volume", 5000))],
                        }
                    )
                    return new_bar
            except Exception as e:
                logger.warning(f"获取最新K线失败 {stock_code}: {e}")

                # 降级: 返回模拟数据
        import numpy as np

        price = 100.0 + np.random.randn() * 0.5

        new_bar = pd.DataFrame(
            {
                "date": [pd.Timestamp.now()],
                "open": [price * 0.99],
                "high": [price * 1.01],
                "low": [price * 0.98],
                "close": [price],
                "volume": [np.random.randint(1000, 10000)],
            }
        )

        return new_bar

    async def batch_calculate(self, stock_codes: list[str], indicator_names: list[str]) -> dict[str, dict[str, Any]]:
        """
        批量计算指标

        Args:
            stock_codes: 股票代码列表
            indicator_names: 指标名称列表

        Returns:
            计算结果字典
        """
        results = {}

        for stock_code in stock_codes:
            stock_results = {}

            # 获取K线数据
            kline_data = await self._get_kline_data(stock_code)

            if kline_data is not None and not kline_data.empty:
                for indicator_name in indicator_names:
                    if indicator_name in self.indicators:
                        indicator = self.indicators[indicator_name]
                        result = indicator.calculate(kline_data)
                        stock_results[indicator_name] = result

            results[stock_code] = stock_results

        return results

    def get_stats(self) -> dict[str, Any]:
        """
        获取推送统计

        Returns:
            统计信息
        """
        return {
            "running": self.running,
            "active_pushers": len(self.push_tasks),
            "cached_stocks": len(self.data_cache),
            "push_interval": self.push_interval,
            "available_indicators": list(self.indicators.keys()),
        }

        # 全局推送器实例


indicator_pusher = IndicatorPusher()
