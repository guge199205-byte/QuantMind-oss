"""KLine service"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..market_config import settings
from ..models import KLine
from ..schemas import KLineCreate, KLineResponse
from .data_source import SinaDataSource, TencentDataSource
from .remote_redis_source import RemoteRedisDataSource

logger = logging.getLogger(__name__)


class KLineService:
    """K线数据服务"""

    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis
        self.primary_source = TencentDataSource()
        self.fallback_source = SinaDataSource()
        self.remote_snapshot_source = RemoteRedisDataSource()

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1d",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        use_cache: bool = True,
    ) -> list[KLineResponse]:
        """获取K线数据"""

        # 1. 尝试从缓存获取
        if use_cache and self.redis:
            cached = await self._get_cached_klines(symbol, interval, limit)
            if cached:
                logger.debug(f"KLine cache hit for {symbol} {interval}")
                return cached

        # 2. 从数据库查询
        klines = await self.list_klines(symbol, interval, start_time, end_time, limit)

        # 3. 如果数据库没有，从数据源获取
        if not klines:
            logger.info(f"Fetching klines from data source for {symbol} {interval}")
            kline_data = await self.primary_source.fetch_kline(symbol, interval, start_time, end_time, limit)
            if not kline_data:
                kline_data = await self.fallback_source.fetch_kline(symbol, interval, start_time, end_time, limit)

            if kline_data:
                # 批量保存
                for data in kline_data:
                    await self.create_kline(KLineCreate(**data))

                klines = await self.list_klines(symbol, interval, start_time, end_time, limit)
            else:
                # 上游 K 线为空时，使用远程快照兜底生成一根“当前K线”
                snap = await self.remote_snapshot_source.fetch_quote(symbol)
                if snap and snap.get("current_price") is not None:
                    ts = snap.get("timestamp") if isinstance(snap.get("timestamp"), datetime) else datetime.now()
                    price = float(snap.get("current_price") or 0.0)
                    open_p = float(snap.get("open_price") or price)
                    high_p = float(snap.get("high_price") or max(open_p, price))
                    low_p = float(snap.get("low_price") or min(open_p, price))
                    close_p = float(snap.get("close_price") or price)
                    volume = int(snap.get("volume") or 0)
                    amount = snap.get("amount")

                    synthetic = KLineCreate(
                        symbol=symbol,
                        interval=interval,
                        timestamp=ts,
                        open_price=open_p,
                        high_price=high_p,
                        low_price=low_p,
                        close_price=close_p,
                        volume=volume,
                        amount=float(amount) if amount is not None else None,
                        change=(price - close_p) if close_p else None,
                        change_percent=((price - close_p) / close_p * 100.0) if close_p else None,
                        turnover_rate=None,
                        data_source="remote_redis",
                    )
                    try:
                        await self.create_kline(synthetic)
                    except Exception as e:
                        logger.warning(f"Create synthetic kline failed for {symbol}: {e}")
                        await self.db.rollback()
                    klines = await self.list_klines(symbol, interval, start_time, end_time, limit)

        # 4. 缓存
        if self.redis and klines:
            await self._cache_klines(symbol, interval, klines)

        return klines

    async def create_kline(self, kline: KLineCreate) -> KLineResponse:
        """创建K线记录"""
        db_kline = KLine(**kline.model_dump())
        self.db.add(db_kline)
        await self.db.commit()
        await self.db.refresh(db_kline)
        return KLineResponse.model_validate(db_kline)

    async def list_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KLineResponse]:
        """查询K线历史"""
        query = select(KLine).filter(and_(KLine.symbol == symbol, KLine.interval == interval))

        if start_time:
            query = query.filter(KLine.timestamp >= start_time)
        if end_time:
            query = query.filter(KLine.timestamp <= end_time)

        query = query.order_by(desc(KLine.timestamp)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        klines = result.scalars().all()

        return [KLineResponse.model_validate(k) for k in klines]

    async def get_latest_kline(self, symbol: str, interval: str) -> KLineResponse | None:
        """获取最新K线"""
        query = (
            select(KLine)
            .filter(and_(KLine.symbol == symbol, KLine.interval == interval))
            .order_by(desc(KLine.timestamp))
            .limit(1)
        )

        result = await self.db.execute(query)
        kline = result.scalar_one_or_none()

        return KLineResponse.model_validate(kline) if kline else None

    async def _get_cached_klines(self, symbol: str, interval: str, limit: int) -> list[KLineResponse] | None:
        """从缓存获取K线"""
        if not self.redis:
            return None

        try:
            cache_key = f"kline:{symbol}:{interval}:{limit}"
            cached_data = await self.redis.get(cache_key)

            if cached_data:
                data_list = json.loads(cached_data)
                return [KLineResponse(**item) for item in data_list]
        except Exception as e:
            logger.error(f"Error getting cached klines: {e}")

        return None

    async def _cache_klines(self, symbol: str, interval: str, klines: list[KLineResponse]) -> None:
        """缓存K线数据"""
        if not self.redis:
            return

        try:
            cache_key = f"kline:{symbol}:{interval}:{len(klines)}"
            cache_data = json.dumps([k.model_dump() for k in klines], default=str)
            await self.redis.setex(cache_key, settings.CACHE_TTL_KLINE, cache_data)
        except Exception as e:
            logger.error(f"Error caching klines: {e}")
