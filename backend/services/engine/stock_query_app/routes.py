"""
股票查询服务FastAPI路由
统一使用FastAPI框架，替换Flask版本
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .services import StockQueryService, StockSearchService

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["stock-query"])

# Market-specific stock_daily_latest table mapping
_MARKET_SDL_TABLE = {
    "A": "stock_daily_latest",
    "CN": "stock_daily_latest",
    "HK": "stock_daily_latest_hk",
    "US": "stock_daily_latest_us",
    "CRYPTO": "stock_daily_latest_crypto",
}

# 服务实例
_query_service = None
_search_service = None


def get_query_service() -> StockQueryService:
    """获取股票查询服务实例"""
    global _query_service
    if _query_service is None:
        _query_service = StockQueryService()
    return _query_service


def get_search_service() -> StockSearchService:
    """获取股票搜索服务实例"""
    global _search_service
    if _search_service is None:
        _search_service = StockSearchService()
    return _search_service

    # 请求模型


class StockQueryRequest(BaseModel):
    symbol: str
    fields: list[str] | None = None


class StockSearchRequest(BaseModel):
    query: str
    limit: int | None = 10


class MarketIndexRequest(BaseModel):
    symbols: list[str] | None = None
    indicators: list[str] | None = None


@router.get("/stocks/search")
async def search_stocks(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, ge=1, le=100, description="返回结果数量限制"),
):
    """搜索股票"""
    logger.info("Stock search request", extra={"query": q, "limit": limit})

    try:
        search_service = get_search_service()
        results = await search_service.search_stocks(q, limit)

        logger.info(
            "Stock search completed",
            extra={"query": q, "results_count": len(results), "limit": limit},
        )

        return {
            "query": q,
            "results": results,
            "total": len(results),
            "timestamp": __import__("datetime").datetime.now().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("Stock search failed", extra={"query": q, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/stocks/all")
async def get_all_stocks(
    market: str = Query("A", description="市场代码: A/CN, HK, US, CRYPTO"),
    enrich: bool = Query(False, description="是否包含 PE/PB/市值等字段"),
    limit: int = Query(10000, ge=1, le=50000, description="返回数量限制"),
):
    """获取指定市场的全部股票列表"""
    market_key = market.upper()
    table = _MARKET_SDL_TABLE.get(market_key, "stock_daily_latest")
    logger.info("Fetching all stocks", extra={"market": market_key, "table": table, "enrich": enrich})

    try:
        from backend.shared.database_pool import get_db

        # Determine name column: CN uses stock_name, others use name
        is_cn = market_key in ("A", "CN")
        name_col = "stock_name" if is_cn else "name"

        if enrich:
            sql = f"""
                SELECT symbol,
                       COALESCE({name_col}, '') AS name,
                       COALESCE(close, 0) AS close,
                       COALESCE(pe_ttm, 0) AS pe,
                       COALESCE(pb, 0) AS pb,
                       COALESCE(roe, 0) AS roe,
                       COALESCE(total_mv, 0) AS "marketCap",
                       COALESCE(float_mv, 0) AS "floatMarketCap",
                       COALESCE(turnover_rate, 0) AS "turnoverRate",
                       COALESCE(pct_change, 0) AS "pctChange",
                       COALESCE(is_st, 0) <> 0 AS "isSt"
                FROM {table}
                ORDER BY symbol
                LIMIT :limit
            """
        else:
            sql = f"""
                SELECT symbol, COALESCE({name_col}, '') AS name
                FROM {table}
                ORDER BY symbol
                LIMIT :limit
            """

        with get_db() as db:
            rows = db.execute(text(sql), {"limit": limit}).fetchall()

        items = []
        for row in rows:
            item = {"symbol": row[0], "name": row[1]}
            if enrich:
                item.update({
                    "close": float(row[2] or 0),
                    "pe": float(row[3] or 0) if row[3] else None,
                    "pb": float(row[4] or 0) if row[4] else None,
                    "roe": float(row[5] or 0) if row[5] else None,
                    "marketCap": float(row[6] or 0) if row[6] else None,
                    "floatMarketCap": float(row[7] or 0) if row[7] else None,
                    "turnoverRate": float(row[8] or 0) if row[8] else None,
                    "pctChange": float(row[9] or 0) if row[9] else None,
                    "isSt": bool(row[10]) if len(row) > 10 else False,
                })
            items.append(item)

        return {
            "items": items,
            "total": len(items),
            "market": market_key,
            "table": table,
        }
    except Exception as e:
        logger.error("Get all stocks failed", extra={"market": market_key, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取股票列表失败: {str(e)}")


@router.get("/stocks/{symbol}")
async def get_stock_info(symbol: str):
    """获取股票详细信息"""
    logger.info("Fetching stock info", extra={"symbol": symbol})

    try:
        query_service = get_query_service()
        stock_info_resp = await query_service.get_stock_info(symbol)
        if not stock_info_resp or not bool(getattr(stock_info_resp, "success", False)):
            raise HTTPException(status_code=500, detail=f"获取股票信息失败: {getattr(stock_info_resp, 'message', 'unknown error')}")

        stock_info = getattr(stock_info_resp, "data", None)
        if not isinstance(stock_info, dict):
            logger.warning("Stock not found", extra={"symbol": symbol})
            raise HTTPException(status_code=404, detail=f"股票 {symbol} 未找到")

        logger.info(
            "Stock info retrieved successfully",
            extra={
                "symbol": symbol,
                "stock_name": stock_info.get("name", ""),
                "price": stock_info.get("price", 0),
            },
        )

        return stock_info_resp.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get stock info failed", extra={"symbol": symbol, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取股票信息失败: {str(e)}")


@router.get("/stocks/{symbol}/quote")
async def get_stock_quote(symbol: str):
    """获取股票实时报价"""
    logger.info("Fetching stock quote", extra={"symbol": symbol})

    try:
        query_service = get_query_service()
        quote = await query_service.get_stock_quote(symbol)

        if not quote:
            logger.warning("Quote not found", extra={"symbol": symbol})
            raise HTTPException(status_code=404, detail=f"股票 {symbol} 报价未找到")

        logger.info(
            "Stock quote retrieved successfully",
            extra={
                "symbol": symbol,
                "price": quote.get("price", 0),
                "change_percent": quote.get("change_percent", 0),
            },
        )

        return quote
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get stock quote failed", extra={"symbol": symbol, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取股票报价失败: {str(e)}")


@router.get("/market/indices")
async def get_market_indices(
    symbols: list[str] | None = Query(None, description="指数代码列表"),
    indicators: list[str] | None = Query(None, description="技术指标列表"),
):
    """获取大盘指数信息"""
    logger.info("Fetching market indices", extra={"symbols": symbols, "indicators": indicators})

    try:
        query_service = get_query_service()
        indices = query_service.get_market_indices(symbols, indicators)

        logger.info(
            "Market indices retrieved successfully",
            extra={"count": len(indices)},
        )

        return {
            "indices": indices,
            "total": len(indices),
            "timestamp": __import__("datetime").datetime.now().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("Get market indices failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取大盘指数失败: {str(e)}")


@router.get("/market/overview")
async def get_market_overview():
    """获取市场概览"""
    logger.info("Fetching market overview")

    try:
        query_service = get_query_service()
        overview = query_service.get_market_overview()

        logger.info("Market overview retrieved successfully")

        return overview
    except Exception as e:
        logger.error("Get market overview failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取市场概览失败: {str(e)}")


"""
注意：企业级金融业务禁止内置任何演示数据接口。
如需数据，请通过真实数据源与本地数据库/数据管理链路提供。
"""
