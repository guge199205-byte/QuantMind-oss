"""
股票搜索接口（API 网关本地索引版）

目标：
1. 避免前端直连第三方行情服务产生 CORS 问题。
2. 通过服务器本地 JSON 索引提供稳定、低延迟的搜索能力。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/stocks", tags=["Stocks"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class StockIndexItem:
    symbol: str
    code: str
    exchange: str
    name: str
    abbr: str = ""
    pinyin: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StockIndexItem:
        symbol = str(raw.get("symbol") or "").strip().upper()
        code = str(raw.get("code") or "").strip()
        exchange = str(raw.get("exchange") or "").strip().upper()
        name = str(raw.get("name") or "").strip()
        abbr = str(raw.get("abbr") or "").strip().lower()
        pinyin = str(raw.get("pinyin") or "").strip().lower()

        if not symbol and code and exchange:
            symbol = f"{code}.{exchange}"
        if not code and symbol and "." in symbol:
            code = symbol.split(".", 1)[0]
        if not exchange and symbol and "." in symbol:
            exchange = symbol.split(".", 1)[1]

        return cls(
            symbol=symbol,
            code=code,
            exchange=exchange,
            name=name,
            abbr=abbr,
            pinyin=pinyin,
        )

    def searchable_text(self) -> str:
        return " ".join(
            [
                self.symbol.lower(),
                self.code.lower(),
                self.name.lower(),
                self.abbr,
                self.pinyin,
            ]
        ).strip()

    def to_result(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "code": self.symbol,  # 前端历史字段沿用 code，统一返回标准代码
            "name": self.name,
            "market": self.exchange,
        }


class StockIndexStore:
    def __init__(self) -> None:
        # 支持多个备选路径，优先使用环境变量，然后尝试容器内挂载路径
        candidate_paths = [
            os.getenv("STOCK_INDEX_JSON_PATH"),
            "/data/stocks/stocks_index.json",  # Docker 挂载路径
            "data/stocks/stocks_index.json",   # 相对路径
            "/app/data/stocks/stocks_index.json",  # 容器内绝对路径
        ]
        self.path = None
        for p in candidate_paths:
            if p and os.path.exists(p):
                self.path = os.path.abspath(p)
                break
        if not self.path:
            # 回退到默认路径（会在 _load_if_needed 中报错）
            self.path = os.path.abspath(os.getenv("STOCK_INDEX_JSON_PATH", "data/stocks/stocks_index.json"))
        self._lock = RLock()
        self._mtime: float = -1.0
        self._items: list[StockIndexItem] = []

    def _load_if_needed(self) -> None:
        with self._lock:
            if not os.path.exists(self.path):
                raise FileNotFoundError(self.path)

            mtime = os.path.getmtime(self.path)
            if mtime == self._mtime:
                return

            with open(self.path, encoding="utf-8") as f:
                payload = json.load(f)

            raw_items = payload.get("items")
            if not isinstance(raw_items, list):
                raise ValueError("stocks_index.json 缺少 items 数组")

            loaded: list[StockIndexItem] = []
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = StockIndexItem.from_dict(raw)
                if item.symbol and item.name:
                    loaded.append(item)

            self._items = loaded
            self._mtime = mtime
            logger.info("已加载股票索引: path=%s count=%s", self.path, len(loaded))

    def search(self, keyword: str, limit: int) -> list[dict[str, Any]]:
        self._load_if_needed()
        k = keyword.strip().lower()
        if not k:
            return []

        starts: list[StockIndexItem] = []
        contains: list[StockIndexItem] = []
        for item in self._items:
            text = item.searchable_text()
            if text.startswith(k) or item.symbol.lower().startswith(k) or item.code.lower().startswith(k):
                starts.append(item)
            elif k in text:
                contains.append(item)

            if len(starts) >= limit:
                break

        merged = (starts + contains)[:limit]
        return [x.to_result() for x in merged]

    def status(self) -> dict[str, Any]:
        exists = os.path.exists(self.path)
        stat = os.stat(self.path) if exists else None
        return {
            "path": self.path,
            "exists": exists,
            "size": stat.st_size if stat else 0,
            "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else None,
            "loaded_count": len(self._items),
        }


stock_index_store = StockIndexStore()


@router.get("/search")
async def search_stocks(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=200, description="最大返回数量"),
):
    try:
        results = stock_index_store.search(keyword=q, limit=limit)
    except FileNotFoundError as exc:
        logger.error("股票索引文件不存在: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "股票索引未就绪，请先在服务器执行构建脚本：" "python backend/services/api/scripts/build_stock_index.py"
            ),
        )
    except Exception as exc:
        logger.error("股票索引搜索失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"股票搜索失败: {exc}")

    return {
        "query": q,
        "results": results,
        "total": len(results),
        "timestamp": _now_iso(),
        "source": "stocks-index-json",
    }


@router.get("/search/status")
async def search_status():
    return {
        "status": "ok",
        "timestamp": _now_iso(),
        "index": stock_index_store.status(),
    }


@router.get("/index-file")
async def get_stock_index_file():
    """返回完整的股票索引 JSON（替代前端的 /data/stocks/stocks_index.json 静态请求）。

    返回结构与 build_stock_index.py 写出的 stocks_index.json 一致：
    items[*]: {symbol, code, exchange, name, abbr, pinyin}
    """
    try:
        stock_index_store._load_if_needed()
        items = [
            {
                "symbol": it.symbol,
                "code": it.code,
                "exchange": it.exchange,
                "name": it.name,
                "abbr": it.abbr,
                "pinyin": it.pinyin,
            }
            for it in stock_index_store._items
        ]
        return {
            "generated_at": _now_iso(),
            "count": len(items),
            "items": items,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="股票索引文件未生成，请运行 build_stock_index.py")


# ---------------------------------------------------------------------------
# 全市场标的清单 — 供"加载全市场"按钮使用
# 直接从 stock_daily_latest* 取最新交易日的所有 distinct symbol，
# 避免依赖离线构建的 stocks_index.json 文件
# ---------------------------------------------------------------------------

_ALL_CACHE: dict[str, Any] = {}
_ALL_CACHE_TTL = 600  # 10 分钟

# Market-specific table mapping
_MARKET_TABLE_MAP = {
    "A": "stock_daily_latest",
    "CN": "stock_daily_latest",
    "HK": "stock_daily_latest_hk",
    "US": "stock_daily_latest_us",
    "CRYPTO": "stock_daily_latest_crypto",
}

# Non-CN markets use 'name' column instead of 'stock_name'
_MARKET_NAME_COL = {
    "A": "stock_name",
    "CN": "stock_name",
    "HK": "name",
    "US": "name",
    "CRYPTO": "name",
}


def _convert_symbol(raw: str) -> tuple[str, str]:
    """SZ300817 -> ('300817.SZ', 'SZ')"""
    s = str(raw or "").strip().upper()
    if not s:
        return "", ""
    if s[:2] in ("SZ", "SH", "BJ") and s[2:].isdigit():
        return f"{s[2:]}.{s[:2]}", s[:2]
    if "." in s:
        code, ex = s.split(".", 1)
        return s, ex
    return s, ""


@router.get("/all")
async def list_all_stocks(
    market: str = Query("A", description="市场代码：A/CN=全部A股, HK=港股, US=美股, CRYPTO=加密货币"),
    enrich: bool = Query(True, description="是否带最新交易日的核心字段：close/pe/pb/total_mv/float_mv/pct_change/turnover_rate/is_st"),
):
    """返回全市场标的列表（来自 stock_daily_latest* 最新交易日）。

    用于前端"加载全市场"功能。结果 10 分钟内做内存缓存。
    enrich=True (默认) 时一并返回核心市场字段，避免前端再次批量查询。
    """
    import time
    from sqlalchemy import text as sql_text

    market_key = (market or "A").strip().upper()
    table_name = _MARKET_TABLE_MAP.get(market_key, "stock_daily_latest")
    name_col = _MARKET_NAME_COL.get(market_key, "stock_name")
    is_cn = market_key in ("A", "CN")

    now = time.time()
    cache_key = f"items_market={market_key}_enrich={enrich}"
    cached_items = _ALL_CACHE.get(cache_key)
    if cached_items and (now - _ALL_CACHE.get(f"ts_{cache_key}", 0)) < _ALL_CACHE_TTL:
        items = cached_items
    else:
        # 用同步 psycopg2 拉一次性扫描（5k 行级别，<200ms）
        from sqlalchemy import create_engine
        from urllib.parse import quote_plus as _q

        db_url = os.getenv("DATABASE_URL", "").strip()
        if not db_url:
            host = os.getenv("DB_MASTER_HOST", "quantmind-db")
            port = os.getenv("DB_MASTER_PORT", "5432")
            user = os.getenv("DB_USER", "quantmind")
            pwd = _q(os.getenv("DB_PASSWORD", "quantmind"))
            name = os.getenv("DB_NAME", "quantmind")
            db_url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"
        elif "asyncpg" in db_url:
            db_url = db_url.replace("asyncpg", "psycopg2")
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        try:
            engine = create_engine(db_url, pool_pre_ping=True)
            with engine.begin() as conn:
                if enrich:
                    # 注：近期交易日的 pe_ttm/total_mv 字段可能为空，
                    # 需要从更早的非空行中回退取值，否则前端表格全部显示为 "-"
                    # CN uses stock_name + listed_days; non-CN uses name, no listed_days
                    if is_cn:
                        rows = conn.execute(
                            sql_text(
                                f"""
                                WITH latest AS (
                                    SELECT DISTINCT ON (symbol)
                                        symbol, {name_col} AS name, close, pct_change,
                                        turnover_rate, is_st, listed_days
                                    FROM {table_name}
                                    WHERE {name_col} IS NOT NULL AND {name_col} <> ''
                                    ORDER BY symbol, trade_date DESC
                                ),
                                fundamentals AS (
                                    SELECT DISTINCT ON (symbol)
                                        symbol, pe_ttm, pb, total_mv, float_mv
                                    FROM {table_name}
                                    WHERE total_mv IS NOT NULL AND total_mv > 0
                                    ORDER BY symbol, trade_date DESC
                                )
                                SELECT
                                    l.symbol, l.name, l.close,
                                    f.pe_ttm, f.pb, f.total_mv, f.float_mv,
                                    l.pct_change, l.turnover_rate, l.is_st, l.listed_days
                                FROM latest l
                                LEFT JOIN fundamentals f USING (symbol)
                                """
                            )
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            sql_text(
                                f"""
                                WITH latest AS (
                                    SELECT DISTINCT ON (symbol)
                                        symbol, {name_col} AS name, close, pct_change,
                                        turnover_rate, is_st
                                    FROM {table_name}
                                    WHERE {name_col} IS NOT NULL AND {name_col} <> ''
                                    ORDER BY symbol, trade_date DESC
                                ),
                                fundamentals AS (
                                    SELECT DISTINCT ON (symbol)
                                        symbol, pe_ttm, pb, total_mv, float_mv
                                    FROM {table_name}
                                    WHERE total_mv IS NOT NULL AND total_mv > 0
                                    ORDER BY symbol, trade_date DESC
                                )
                                SELECT
                                    l.symbol, l.name, l.close,
                                    f.pe_ttm, f.pb, f.total_mv, f.float_mv,
                                    l.pct_change, l.turnover_rate, l.is_st
                                FROM latest l
                                LEFT JOIN fundamentals f USING (symbol)
                                """
                            )
                        ).fetchall()
                else:
                    rows = conn.execute(
                        sql_text(
                            f"""
                            SELECT DISTINCT ON (symbol)
                                symbol, {name_col} AS name
                            FROM {table_name}
                            WHERE {name_col} IS NOT NULL AND {name_col} <> ''
                            ORDER BY symbol, trade_date DESC
                            """
                        )
                    ).fetchall()
        except Exception as exc:  # noqa: BLE001
            logger.error("list_all_stocks DB query failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"DB query failed: {exc}")

        items: list[dict[str, Any]] = []
        for r in rows:
            raw_symbol = r[0]
            raw_name = r[1]
            # Non-CN symbols don't have exchange suffix, add market hint
            if is_cn:
                sym, exch = _convert_symbol(raw_symbol)
            else:
                sym = str(raw_symbol).strip()
                exch = market_key
            if not sym:
                continue
            row: dict[str, Any] = {
                "symbol": sym,
                "code": sym.split(".", 1)[0] if "." in sym else sym,
                "name": str(raw_name).strip(),
                "exchange": exch,
            }
            if enrich:
                # total_mv/float_mv 单位为元 → 转为亿元便于前端显示
                total_mv = float(r[5]) if len(r) > 5 and r[5] is not None else None
                float_mv = float(r[6]) if len(r) > 6 and r[6] is not None else None
                row.update({
                    "close": float(r[2]) if r[2] is not None else None,
                    "pe": float(r[3]) if r[3] is not None else None,
                    "pb": float(r[4]) if r[4] is not None else None,
                    "marketCap": (total_mv / 1e8) if total_mv else None,
                    "floatMarketCap": (float_mv / 1e8) if float_mv else None,
                    "pctChange": float(r[7]) if len(r) > 7 and r[7] is not None else None,
                    "turnoverRate": float(r[8]) if len(r) > 8 and r[8] is not None else None,
                    "isSt": bool(r[9]) if len(r) > 9 and r[9] is not None else False,
                    "listedDays": int(r[10]) if len(r) > 10 and r[10] is not None else None,
                })
            items.append(row)

        _ALL_CACHE[cache_key] = items
        _ALL_CACHE[f"ts_{cache_key}"] = now

    # 市场过滤（仅 CN 子交易所过滤）
    if market_key in ("SH", "SZ", "BJ"):
        items = [x for x in items if x["exchange"] == market_key]

    return {
        "market": market_key,
        "count": len(items),
        "items": items,
        "table": table_name,
        "cached_at": datetime.fromtimestamp(_ALL_CACHE.get(f"ts_{cache_key}", now), timezone.utc).isoformat(),
    }
