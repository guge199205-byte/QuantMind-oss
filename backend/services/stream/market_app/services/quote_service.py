"""Quote service"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..market_config import settings
from ..models import Quote
from ..schemas import QuoteCreate, QuoteResponse
from .data_source import (
    DataSourceAdapter,
    SinaDataSource,
    TencentDataSource,
)
from .ifind_source import IFindDataSource
from .remote_redis_source import RemoteRedisDataSource

logger = logging.getLogger(__name__)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class QuoteService:
    """实时行情服务"""

    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis

        # 初始化数据源
        self.data_sources = {
            "tencent": TencentDataSource(),
            "sina": SinaDataSource(),
            "ifind": IFindDataSource(),
            "remote_redis": RemoteRedisDataSource(),
        }
        self.default_source = settings.DEFAULT_SOURCE

    async def get_quote(
        self, symbol: str, source: str | None = None, use_cache: bool = True
    ) -> QuoteResponse | None:
        """获取实时行情"""

        # 1. 尝试从缓存获取
        if use_cache and self.redis:
            cached = await self._get_cached_quote(symbol)
            if cached:
                logger.debug(f"Quote cache hit for {symbol}")
                return cached

        # 2. 优先读取 WS 推送链路最近落库的数据，减少 WS/REST 时点差异
        recent = await self._get_recent_quote(symbol, max_age_seconds=5)
        if recent:
            return recent

        # 3. 从数据源获取
        data_source = self._get_data_source(source)
        quote_data = await data_source.fetch_quote(symbol)

        if not quote_data:
            logger.warning(f"Failed to fetch quote for {symbol}")
            return None

        # 4. 保存到数据库
        quote_obj = await self.create_quote(QuoteCreate(**quote_data))

        # 5. 缓存
        if self.redis and quote_obj:
            await self._cache_quote(quote_obj)

        return quote_obj

    async def create_quote(self, quote: QuoteCreate) -> QuoteResponse:
        """创建行情记录"""
        data = quote.model_dump()
        # 过滤掉不在数据库模型中的字段
        db_fields = {c.name for c in Quote.__table__.columns}
        filtered_data = {k: v for k, v in data.items() if k in db_fields}

        db_quote = Quote(**filtered_data)
        self.db.add(db_quote)
        await self.db.commit()
        await self.db.refresh(db_quote)
        return QuoteResponse.model_validate(db_quote)

    async def list_quotes(
        self,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QuoteResponse]:
        """查询行情历史"""
        query = select(Quote)

        if symbol:
            query = query.filter(Quote.symbol == symbol)
        if start_time:
            query = query.filter(Quote.timestamp >= start_time)
        if end_time:
            query = query.filter(Quote.timestamp <= end_time)

        query = query.order_by(desc(Quote.timestamp)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        quotes = result.scalars().all()

        return [QuoteResponse.model_validate(q) for q in quotes]

    async def get_latest_quote(self, symbol: str) -> QuoteResponse | None:
        """获取最新行情"""
        query = select(Quote).filter(Quote.symbol == symbol).order_by(desc(Quote.timestamp)).limit(1)
        result = await self.db.execute(query)
        quote = result.scalar_one_or_none()

        return QuoteResponse.model_validate(quote) if quote else None

    async def _get_recent_quote(self, symbol: str, max_age_seconds: int = 5) -> QuoteResponse | None:
        latest = await self.get_latest_quote(symbol)
        if not latest:
            return None
        age = (datetime.now(timezone.utc) - _as_utc_aware(latest.timestamp)).total_seconds()
        return latest if age <= max_age_seconds else None

    def _get_data_source(self, source: str | None = None) -> DataSourceAdapter:
        """获取数据源"""
        source_name = source or self.default_source
        adapter = self.data_sources.get(source_name)
        if not adapter:
            allowed = ",".join(sorted(self.data_sources.keys()))
            raise ValueError(f"不支持的数据源: {source_name}，可选: {allowed}")
        return adapter

    async def _get_cached_quote(self, symbol: str) -> QuoteResponse | None:
        """从缓存获取行情"""
        if not self.redis:
            return None

        try:
            cache_key = f"quote:{symbol}"
            cached_data = await self.redis.get(cache_key)

            if cached_data:
                data = json.loads(cached_data)
                return QuoteResponse(**data)
        except Exception as e:
            logger.error(f"Error getting cached quote: {e}")

        return None

    async def _cache_quote(self, quote: QuoteResponse) -> None:
        """缓存行情"""
        if not self.redis:
            return

        try:
            cache_key = f"quote:{quote.symbol}"
            cache_data = quote.model_dump_json()
            await self.redis.setex(cache_key, settings.CACHE_TTL_QUOTE, cache_data)
        except Exception as e:
            logger.error(f"Error caching quote: {e}")
