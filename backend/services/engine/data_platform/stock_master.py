"""
股票主数据 (stocks 表) 同步/查询服务
===================================

提供两类能力：

1. refresh_market(market, db_url) — 从 baostock(A) / akshare(HK/US) 抓全量股票列表，
   带行业 / 板块 / 交易所信息，UPSERT 进 stocks 表。
2. list_stocks / facets — 给前端按 exchange/industry/sector 筛选用。

设计要点：
- symbol 全部归一化为 ``600519.SH`` / ``00700.HK`` / ``AAPL`` 大写形式（业内最常用）；
  各 adapter 内部各自再转换成自己的格式（baostock=sh.600519, qlib=sh600519 等）。
- HK / US 在外网不通畅时也能优雅退到 "已知核心列表"，避免一键同步彻底用不了。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具：symbol 归一化
# ---------------------------------------------------------------------------
def _normalize_a(code: str) -> str:
    s = str(code or "").strip().upper().replace(" ", "")
    if not s:
        return s
    if "." in s:
        return s
    # sh.600519 / sz.000001
    if s[:3] in ("SH.", "SZ.", "BJ."):
        return f"{s[3:]}.{s[:2]}"
    if s[:2] in ("SH", "SZ", "BJ") and len(s) >= 8:
        return f"{s[2:]}.{s[:2]}"
    if s.isdigit() and len(s) == 6:
        if s.startswith(("600", "601", "603", "605", "688", "689", "900")):
            return f"{s}.SH"
        if s.startswith(("83", "87", "88", "92", "43")):
            return f"{s}.BJ"
        return f"{s}.SZ"
    return s


def _normalize_hk(code: str) -> str:
    s = str(code or "").strip().upper().replace(" ", "")
    if not s:
        return s
    if s.endswith(".HK"):
        return s.zfill(8)  # 00700.HK
    if s.isdigit():
        return f"{s.zfill(5)}.HK"
    return s


def _normalize_us(code: str) -> str:
    return str(code or "").strip().upper().replace(" ", "")


def _exchange_of(symbol: str, market: str) -> str:
    if market == "A":
        if symbol.endswith(".SH"):
            return "SH"
        if symbol.endswith(".SZ"):
            return "SZ"
        if symbol.endswith(".BJ"):
            return "BJ"
        return "OTHER"
    if market == "HK":
        return "HK"
    if market == "US":
        return "US"
    return market


# ---------------------------------------------------------------------------
# 抓取：baostock A 股全量 + 行业
# ---------------------------------------------------------------------------
def _fetch_a_baostock() -> pd.DataFrame:
    """
    返回 columns=[symbol, name, exchange, industry, sector, list_date]
    """
    import baostock as bs

    rs = bs.login()
    if rs.error_code != "0":
        raise RuntimeError(f"baostock login failed: {rs.error_msg}")
    try:
        # 1. 全量证券列表（取今天前一交易日）
        today = date.today().strftime("%Y-%m-%d")
        sr = bs.query_all_stock(day=today)
        if sr.error_code != "0":
            # 退回到前一交易日
            sr = bs.query_all_stock(day=(date.today().toordinal() - 1))  # type: ignore
        rows = []
        while sr.error_code == "0" and sr.next():
            rows.append(sr.get_row_data())
        if not rows:
            raise RuntimeError("baostock query_all_stock 空")
        df_all = pd.DataFrame(rows, columns=sr.fields)
        # baostock code 形如 sh.600519
        df_all = df_all[df_all["code"].str.startswith(("sh.", "sz.", "bj."))]
        df_all["symbol"] = df_all["code"].apply(_normalize_a)
        df_all = df_all.rename(columns={"code_name": "name"})[["symbol", "name"]]

        # 2. 行业分类
        ind = bs.query_stock_industry()
        ind_rows = []
        while ind.error_code == "0" and ind.next():
            ind_rows.append(ind.get_row_data())
        df_ind = pd.DataFrame(ind_rows, columns=ind.fields) if ind_rows else pd.DataFrame()
        if not df_ind.empty:
            df_ind["symbol"] = df_ind["code"].apply(_normalize_a)
            df_ind = df_ind[["symbol", "industry"]]
        else:
            df_ind = pd.DataFrame(columns=["symbol", "industry"])

        # 3. 上证 50 / 沪深 300 / 中证 500 / 科创板 sector 标记
        sectors: dict[str, list[str]] = {}
        for sec_name, fn in [
            ("SSE50", bs.query_sz50_stocks),
            ("HS300", bs.query_hs300_stocks),
            ("ZZ500", bs.query_zz500_stocks),
        ]:
            try:
                rs2 = fn()
                while rs2.error_code == "0" and rs2.next():
                    code = _normalize_a(rs2.get_row_data()[1])
                    sectors.setdefault(code, []).append(sec_name)
            except Exception as exc:
                logger.warning("baostock %s failed: %s", sec_name, exc)
        sec_rows = [{"symbol": k, "sector": ",".join(v)} for k, v in sectors.items()]
        df_sec = pd.DataFrame(sec_rows) if sec_rows else pd.DataFrame(columns=["symbol", "sector"])

        df = df_all.merge(df_ind, on="symbol", how="left").merge(df_sec, on="symbol", how="left")
        df["exchange"] = df["symbol"].apply(lambda s: _exchange_of(s, "A"))
        df["list_date"] = None
        df["industry"] = df["industry"].fillna("")
        df["sector"] = df["sector"].fillna("")
        return df[["symbol", "name", "exchange", "industry", "sector", "list_date"]]
    finally:
        bs.logout()


def _fetch_a_akshare() -> pd.DataFrame:
    """akshare 兜底：拿 A 股名称 + 行业；东方财富 push2 现被封时可能失败。"""
    import akshare as ak

    df_em = ak.stock_info_a_code_name()  # 列：code, name
    df_em["symbol"] = df_em["code"].apply(_normalize_a)
    df_em["exchange"] = df_em["symbol"].apply(lambda s: _exchange_of(s, "A"))
    df_em["industry"] = ""
    df_em["sector"] = ""
    df_em["list_date"] = None
    return df_em[["symbol", "name", "exchange", "industry", "sector", "list_date"]]


def _fetch_hk_akshare() -> pd.DataFrame:
    import akshare as ak

    try:
        df = ak.stock_hk_spot_em()  # 列：代码, 名称, ...
        df["symbol"] = df["代码"].astype(str).apply(_normalize_hk)
        df["name"] = df["名称"]
    except Exception as exc:
        logger.warning("akshare stock_hk_spot_em failed: %s", exc)
        df = pd.DataFrame(
            [
                ("00700.HK", "腾讯控股"),
                ("09988.HK", "阿里巴巴-SW"),
                ("00388.HK", "香港交易所"),
                ("01299.HK", "友邦保险"),
                ("00939.HK", "建设银行"),
                ("00005.HK", "汇丰控股"),
                ("00941.HK", "中国移动"),
                ("01810.HK", "小米集团-W"),
                ("03690.HK", "美团-W"),
                ("09618.HK", "京东集团-SW"),
            ],
            columns=["symbol", "name"],
        )
    df["exchange"] = "HK"
    df["industry"] = ""
    df["sector"] = ""
    df["list_date"] = None
    return df[["symbol", "name", "exchange", "industry", "sector", "list_date"]]


def _fetch_us_akshare() -> pd.DataFrame:
    import akshare as ak

    try:
        df = ak.stock_us_spot_em()  # 列：代码, 名称, 最新价 ...
        df["symbol"] = df["代码"].astype(str).str.split(".").str[-1].apply(_normalize_us)
        df["name"] = df["名称"]
    except Exception as exc:
        logger.warning("akshare stock_us_spot_em failed: %s", exc)
        df = pd.DataFrame(
            [
                ("AAPL", "Apple"),
                ("MSFT", "Microsoft"),
                ("NVDA", "NVIDIA"),
                ("GOOGL", "Alphabet"),
                ("TSLA", "Tesla"),
                ("AMZN", "Amazon"),
                ("META", "Meta Platforms"),
                ("AMD", "AMD"),
                ("NFLX", "Netflix"),
                ("AVGO", "Broadcom"),
            ],
            columns=["symbol", "name"],
        )
    df["exchange"] = "US"
    df["industry"] = ""
    df["sector"] = ""
    df["list_date"] = None
    return df[["symbol", "name", "exchange", "industry", "sector", "list_date"]]


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
_UPSERT_SQL = text(
    """
    INSERT INTO stocks (symbol, name, exchange, industry, sector, list_date, is_active, updated_at)
    VALUES (:symbol, :name, :exchange, :industry, :sector, :list_date, TRUE, now())
    ON CONFLICT (symbol) DO UPDATE
       SET name = EXCLUDED.name,
           exchange = EXCLUDED.exchange,
           industry = CASE WHEN EXCLUDED.industry <> '' THEN EXCLUDED.industry ELSE stocks.industry END,
           sector = CASE WHEN EXCLUDED.sector <> '' THEN EXCLUDED.sector ELSE stocks.sector END,
           list_date = COALESCE(EXCLUDED.list_date, stocks.list_date),
           is_active = TRUE,
           updated_at = now()
    """
)


def refresh_market(market: str, engine: Engine) -> dict[str, Any]:
    """
    抓全量股票列表并 UPSERT 进 stocks 表。
    返回 {market, source, inserted_or_updated, total_rows}。
    """
    market = market.upper()
    if market == "A":
        try:
            df = _fetch_a_baostock()
            source = "baostock"
        except Exception as exc:
            logger.warning("baostock A list failed: %s; fallback akshare", exc)
            df = _fetch_a_akshare()
            source = "akshare"
    elif market == "HK":
        df = _fetch_hk_akshare()
        source = "akshare"
    elif market == "US":
        df = _fetch_us_akshare()
        source = "akshare"
    else:
        raise ValueError(f"market 不支持: {market}")

    if df is None or df.empty:
        return {"market": market, "source": source, "inserted_or_updated": 0, "total_rows": 0}

    df = df.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"])
    records = df.to_dict(orient="records")
    with engine.begin() as conn:
        # 分批 executemany
        BATCH = 500
        for i in range(0, len(records), BATCH):
            conn.execute(_UPSERT_SQL, records[i : i + BATCH])
    return {
        "market": market,
        "source": source,
        "inserted_or_updated": len(records),
        "total_rows": len(records),
    }


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
def list_stocks(
    engine: Engine,
    *,
    market: Optional[str] = None,
    exchange: Optional[str] = None,
    industry: Optional[str] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    only_active: bool = True,
) -> dict[str, Any]:
    where: list[str] = []
    params: dict[str, Any] = {}
    if only_active:
        where.append("is_active = TRUE")
    if market:
        m = market.upper()
        if m == "A":
            where.append("exchange IN ('SH','SZ','BJ')")
        elif m == "HK":
            where.append("exchange = 'HK'")
        elif m == "US":
            where.append("exchange = 'US'")
    if exchange:
        where.append("exchange = :exchange")
        params["exchange"] = exchange.upper()
    if industry:
        where.append("industry = :industry")
        params["industry"] = industry
    if sector:
        where.append("sector ILIKE :sector_like")
        params["sector_like"] = f"%{sector}%"
    if search:
        where.append("(symbol ILIKE :search OR name ILIKE :search)")
        params["search"] = f"%{search}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.begin() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM stocks {where_sql}"), params
        ).scalar() or 0
        rows = conn.execute(
            text(
                f"SELECT symbol, name, exchange, industry, sector, list_date "
                f"FROM stocks {where_sql} ORDER BY symbol LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": int(limit), "offset": int(offset)},
        ).fetchall()
    items = [
        {
            "symbol": r[0],
            "name": r[1],
            "exchange": r[2],
            "industry": r[3] or "",
            "sector": r[4] or "",
            "list_date": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]
    return {"total": int(total), "items": items}


def list_symbols(
    engine: Engine,
    *,
    market: Optional[str] = None,
    exchange: Optional[str] = None,
    industry: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = 5000,
) -> list[str]:
    """只返回 symbol 列表，给 sweep 用。"""
    data = list_stocks(
        engine, market=market, exchange=exchange,
        industry=industry, sector=sector,
        limit=limit, offset=0,
    )
    return [it["symbol"] for it in data["items"]]


def facets(engine: Engine, market: Optional[str] = None) -> dict[str, Any]:
    """返回该市场的 exchange / industry / sector distinct 列表。"""
    market_clause = ""
    params: dict[str, Any] = {}
    if market:
        m = market.upper()
        if m == "A":
            market_clause = "WHERE exchange IN ('SH','SZ','BJ')"
        elif m == "HK":
            market_clause = "WHERE exchange = 'HK'"
        elif m == "US":
            market_clause = "WHERE exchange = 'US'"

    with engine.begin() as conn:
        exchanges = [r[0] for r in conn.execute(
            text(f"SELECT DISTINCT exchange FROM stocks {market_clause} "
                 f"  AND exchange <> '' ORDER BY exchange".replace("WHERE  AND", "WHERE")
                 if market_clause else
                 "SELECT DISTINCT exchange FROM stocks WHERE exchange <> '' ORDER BY exchange"),
            params,
        ).fetchall() if r[0]]
        industries = [r[0] for r in conn.execute(
            text(f"SELECT DISTINCT industry FROM stocks {market_clause} "
                 f"  AND industry <> '' ORDER BY industry".replace("WHERE  AND", "WHERE")
                 if market_clause else
                 "SELECT DISTINCT industry FROM stocks WHERE industry <> '' ORDER BY industry"),
            params,
        ).fetchall() if r[0]]
        sectors_raw = [r[0] for r in conn.execute(
            text(f"SELECT DISTINCT sector FROM stocks {market_clause} "
                 f"  AND sector <> '' ORDER BY sector".replace("WHERE  AND", "WHERE")
                 if market_clause else
                 "SELECT DISTINCT sector FROM stocks WHERE sector <> '' ORDER BY sector"),
            params,
        ).fetchall() if r[0]]
        total = conn.execute(
            text(f"SELECT count(*) FROM stocks {market_clause}"),
            params,
        ).scalar() or 0
        last_update = conn.execute(
            text(f"SELECT max(updated_at) FROM stocks {market_clause}"),
            params,
        ).scalar()

    # sector 可能是 "SSE50,HS300" 多值组合，拆开
    sector_set: set[str] = set()
    for s in sectors_raw:
        for piece in str(s).split(","):
            p = piece.strip()
            if p:
                sector_set.add(p)

    return {
        "market": market,
        "exchanges": exchanges,
        "industries": industries,
        "sectors": sorted(sector_set),
        "total": int(total),
        "last_update": last_update.isoformat() if last_update else None,
    }
