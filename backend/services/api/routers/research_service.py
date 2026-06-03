"""投研聚合服务层（保持路由契约不变，仅拆分查询与序列化逻辑）。"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session
from backend.shared.redis_sentinel_client import get_redis_sentinel_client
from backend.shared.stock_utils import StockCodeUtil

_UNIVERSE_CACHE_TTL_SECONDS = 90
_UNIVERSE_CACHE_MAX_ENTRIES = 64
_UNIVERSE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SDL_CACHE_TTL_SECONDS = 120
_SDL_CACHE_MAX_ENTRIES = 512
_SDL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SDL_REDIS_YEAR = int(os.getenv("RESEARCH_SDL_REDIS_YEAR", "2026"))
_SDL_REDIS_TTL_SECONDS = int(os.getenv("RESEARCH_SDL_REDIS_TTL_SECONDS", str(36 * 3600)))

# Market-specific stock table mapping
_MARKET_SDL_TABLE: dict[str, str] = {
    "CN": "stock_daily_latest",
    "HK": "stock_daily_latest_hk",
    "US": "stock_daily_latest_us",
    "CRYPTO": "stock_daily_latest_crypto",
}


def _get_sdl_table(market: str | None = None) -> str:
    """Return the stock_daily_latest table name for the given market."""
    if market:
        key = market.upper()
        if key in _MARKET_SDL_TABLE:
            return _MARKET_SDL_TABLE[key]
    return "stock_daily_latest"


def _redis_get_json(key: str) -> dict[str, Any] | None:
    try:
        redis = get_redis_sentinel_client()
        raw = redis.get(key)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _redis_set_json(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    try:
        redis = get_redis_sentinel_client()
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        redis.setex(key, ttl_seconds, payload)
    except Exception:
        return


def _sdl_redis_key(trade_date: date) -> str:
    return f"qm:research:sdl:{trade_date.isoformat()}:v2"


async def _load_sdl_day_map(session, trade_date: date, market: str | None = None) -> dict[str, dict[str, Any]]:
    if trade_date.year != _SDL_REDIS_YEAR:
        return {}

    sdl_table = _get_sdl_table(market)
    cache_key = _sdl_redis_key(trade_date) + f":{market or 'CN'}"
    cached = _redis_get_json(cache_key)
    if cached and "symbols" in cached and isinstance(cached["symbols"], dict):
        symbols = cached["symbols"]
        return symbols if isinstance(symbols, dict) else {}

    # Use 'name' column for non-CN markets, 'stock_name' for CN
    is_cn = not market or market.upper() == "CN"
    name_col = "stock_name" if is_cn else "name"
    sql = f"""
        SELECT
            symbol,
            COALESCE({name_col}, '') AS stock_name,
            COALESCE(industry, '') AS industry,
            COALESCE(close, 0) AS close_price,
            COALESCE(pe_ttm, 0) AS pe,
            COALESCE(pb, 0) AS pb,
            COALESCE(roe, 0) AS roe,
            COALESCE(adj_factor, 1) AS adj_factor,
            COALESCE(turnover_rate, 0) * 100 AS turnover_rate,
            COALESCE(amount, 0) AS amount,
            COALESCE(total_mv, 0) AS total_mv,
            COALESCE(float_mv, 0) AS float_mv,
            COALESCE(listed_days, 0) AS listed_days,
            COALESCE(is_st, 0) <> 0 AS is_st,
            COALESCE(idx_hs300, 0) <> 0 AS is_hs300,
            0 <> 0 AS is_csi500,
            COALESCE(idx_zz1000, 0) <> 0 AS is_csi1000,
            COALESCE(pct_change, 0) AS latest_change_pct,
            return_1d,
            return_3d,
            COALESCE(ma5, 0) AS ma5,
            COALESCE(ma10, 0) AS ma10,
            COALESCE(ma_gap_5, 0) AS ma_gap_5,
            COALESCE(ma_gap_10, 0) AS ma_gap_10,
            COALESCE(ma_gap_20, 0) AS ma_gap_20,
            COALESCE(rsi_14, rsi_6, 0) AS rsi,
            COALESCE(rsi_14, 0) AS rsi_14,
            COALESCE(vol_atr_14, 0) AS atr,
            COALESCE(macd_hist, 0) AS macd_hist,
            COALESCE(volume_ratio_5, 0) AS volume_ratio_5,
            COALESCE(volume_ratio_20, 0) AS volume_ratio_20,
            CASE WHEN COALESCE(volume_trend_3d, false) THEN 1 ELSE 0 END AS volume_trend_3d,
            COALESCE(main_flow, 0) AS main_flow,
            COALESCE(flow_net_amount, 0) AS flow_net_amount,
            COALESCE(inst_ownership, 0) AS inst_ownership,
            COALESCE(profit_growth, 0) AS profit_growth,
            COALESCE(
              (
                SELECT to_jsonb(array_agg(tag))
                FROM (
                  SELECT tag
                  FROM (
                    VALUES
                      ('AI', COALESCE(concept_ai, 0)),
                      ('芯片', COALESCE(concept_chip, 0)),
                      ('新能源', COALESCE(concept_new_energy, 0)),
                      ('光伏', COALESCE(concept_pv, 0)),
                      ('锂电', COALESCE(concept_lithium, 0)),
                      ('军工', COALESCE(concept_military, 0)),
                      ('医药', COALESCE(concept_medical, 0)),
                      ('金融科技', COALESCE(concept_fintech, 0)),
                      ('消费', COALESCE(concept_consumption, 0)),
                      ('国企改革', COALESCE(concept_state_owned, 0))
                  ) AS concept_scores(tag, score)
                  WHERE score > 0
                  ORDER BY score DESC
                  LIMIT 3
                ) ranked_tags
              ),
              '[]'::jsonb
            ) AS concept_tags,
            COALESCE(
              to_jsonb(array_remove(ARRAY[
                CASE WHEN COALESCE(idx_hs300, 0) <> 0 THEN '沪深300' END,
                CASE WHEN 0 <> 0 THEN '中证500' END,
                CASE WHEN COALESCE(idx_zz1000, 0) <> 0 THEN '中证1000' END,
                CASE WHEN COALESCE(idx_chinext, 0) <> 0 THEN '创业板指数' END,
                CASE WHEN COALESCE(idx_margin, 0) <> 0 THEN '两融标的' END,
                CASE WHEN COALESCE(idx_all, 0) <> 0 THEN '全市场' END
              ]::text[], NULL)),
              '[]'::jsonb
            ) AS index_tags,
            COALESCE(consecutive_limit_up_days, 0) AS consecutive_limit_up_days_sdl
        FROM {sdl_table}
        WHERE trade_date = :trade_date
          AND volume > 0
    """
    res = await session.execute(text(sql), {"trade_date": trade_date})
    symbol_map: dict[str, dict[str, Any]] = {}
    for row in res.mappings():
        payload = dict(row)
        symbol = StockCodeUtil.to_prefix(str(payload.get("symbol") or ""))
        if symbol:
            symbol_map[symbol] = payload

    _redis_set_json(
        cache_key,
        {"trade_date": trade_date.isoformat(), "symbols": symbol_map, "created_at": datetime.now().isoformat()},
        _SDL_REDIS_TTL_SECONDS,
    )
    return symbol_map


def _get_local_cache(cache: dict[str, tuple[float, dict[str, Any]]], key: str, ttl_seconds: int) -> dict[str, Any] | None:
    now = time.monotonic()
    cached = cache.get(key)
    if not cached:
        return None
    if (now - cached[0]) > ttl_seconds:
        cache.pop(key, None)
        return None
    return cached[1]


def _set_local_cache(
    cache: dict[str, tuple[float, dict[str, Any]]], key: str, payload: dict[str, Any], max_entries: int
) -> None:
    cache[key] = (time.monotonic(), payload)
    if len(cache) > max_entries:
        oldest_key = min(cache.items(), key=lambda kv: kv[1][0])[0]
        cache.pop(oldest_key, None)


def _norm_symbol_sql(symbol_expr: str) -> str:
    return f"""
        CASE
            WHEN {symbol_expr} ~* '^(SH|SZ|BJ)[0-9]{{6}}$' THEN UPPER({symbol_expr})
            WHEN {symbol_expr} ~* '^[0-9]{{6}}\\.(SH|SZ|BJ)$' THEN UPPER(RIGHT({symbol_expr}, 2)) || LEFT({symbol_expr}, 6)
            WHEN {symbol_expr} ~ '^[0-9]{{6}}$' AND LEFT({symbol_expr}, 1) IN ('6', '9') THEN 'SH' || {symbol_expr}
            WHEN {symbol_expr} ~ '^[0-9]{{6}}$' AND LEFT({symbol_expr}, 1) IN ('4', '8') THEN 'BJ' || {symbol_expr}
            WHEN {symbol_expr} ~ '^[0-9]{{6}}$' THEN 'SZ' || {symbol_expr}
            ELSE UPPER({symbol_expr})
        END
    """


_SDL_SELECT_BY_RUN_DATE = """
    COALESCE(sdl_run.stock_name, '') AS stock_name,
    COALESCE(sdl_run.industry, '') AS industry,
    COALESCE(sdl_run.close, 0) AS close_price,
    COALESCE(sdl_run.pe_ttm, 0) AS pe,
    COALESCE(sdl_run.pb, 0) AS pb,
    COALESCE(sdl_run.roe, 0) AS roe,
    COALESCE(sdl_run.adj_factor, 1) AS adj_factor,
    COALESCE(sdl_run.turnover_rate, 0) * 100 AS turnover_rate,
    COALESCE(sdl_run.amount, 0) AS amount,
    COALESCE(sdl_run.total_mv, 0) AS total_mv,
    COALESCE(sdl_run.float_mv, 0) AS float_mv,
    COALESCE(sdl_run.listed_days, 0) AS listed_days,
    COALESCE(sdl_run.is_st, 0) <> 0 AS is_st,
    COALESCE(sdl_run.idx_hs300, 0) <> 0 AS is_hs300,
    0 <> 0 AS is_csi500,
    COALESCE(sdl_run.idx_zz1000, 0) <> 0 AS is_csi1000,
    COALESCE(sdl_run.pct_change, 0) AS latest_change_pct,
    CASE
        WHEN NULLIF(sdl_run.close, 0) IS NULL OR sdl_run.close_next_1d IS NULL THEN NULL
        ELSE sdl_run.close_next_1d / NULLIF(sdl_run.close, 0) - 1
    END AS return_1d,
    CASE
        WHEN NULLIF(sdl_run.close, 0) IS NULL OR sdl_run.close_next_3d IS NULL THEN NULL
        ELSE sdl_run.close_next_3d / NULLIF(sdl_run.close, 0) - 1
    END AS return_3d,
    COALESCE(sdl_run.ma5, 0) AS ma5,
    COALESCE(sdl_run.ma10, 0) AS ma10,
    COALESCE(sdl_run.ma_gap_5, 0) AS ma_gap_5,
    COALESCE(sdl_run.ma_gap_10, 0) AS ma_gap_10,
    COALESCE(sdl_run.ma_gap_20, 0) AS ma_gap_20,
    COALESCE(sdl_run.rsi_14, sdl_run.rsi_6, 0) AS rsi,
    COALESCE(sdl_run.rsi_14, 0) AS rsi_14,
    COALESCE(sdl_run.vol_atr_14, 0) AS atr,
    COALESCE(sdl_run.macd_hist, 0) AS macd_hist,
    COALESCE(sdl_run.volume_ratio_5, 0) AS volume_ratio_5,
    COALESCE(sdl_run.volume_ratio_20, 0) AS volume_ratio_20,
    CASE
        WHEN sdl_run.volume_trend_3d IS NOT NULL THEN CASE WHEN sdl_run.volume_trend_3d THEN 1.0 ELSE 0.0 END
        ELSE sdl_run.volume_trend_3d_calc
    END AS volume_trend_3d,
    COALESCE(sdl_run.main_flow, 0) AS main_flow,
    COALESCE(sdl_run.flow_net_amount, 0) AS flow_net_amount,
    COALESCE(sdl_run.inst_ownership, 0) AS inst_ownership,
    COALESCE(sdl_run.profit_growth, 0) AS profit_growth,
    COALESCE(
      (
        SELECT to_jsonb(array_agg(tag))
        FROM (
          SELECT tag
          FROM (
            VALUES
              ('AI', COALESCE(sdl_run.concept_ai, 0)),
              ('芯片', COALESCE(sdl_run.concept_chip, 0)),
              ('新能源', COALESCE(concept_new_energy, 0)),
              ('光伏', COALESCE(sdl_run.concept_pv, 0)),
              ('锂电', COALESCE(sdl_run.concept_lithium, 0)),
              ('军工', COALESCE(sdl_run.concept_military, 0)),
              ('医药', COALESCE(sdl_run.concept_medical, 0)),
              ('金融科技', COALESCE(sdl_run.concept_fintech, 0)),
              ('消费', COALESCE(sdl_run.concept_consumption, 0)),
              ('国企改革', COALESCE(sdl_run.concept_state_owned, 0))
          ) AS concept_scores(tag, score)
          WHERE score > 0
          ORDER BY score DESC
          LIMIT 3
        ) ranked_tags
      ),
      '[]'::jsonb
    ) AS concept_tags,
    COALESCE(
      to_jsonb(array_remove(ARRAY[
        CASE WHEN COALESCE(sdl_run.idx_hs300, 0) <> 0 THEN '沪深300' END,
        CASE WHEN 0 <> 0 THEN '中证500' END,
        CASE WHEN COALESCE(sdl_run.idx_zz1000, 0) <> 0 THEN '中证1000' END,
        CASE WHEN COALESCE(sdl_run.idx_chinext, 0) <> 0 THEN '创业板指数' END,
        CASE WHEN COALESCE(sdl_run.idx_margin, 0) <> 0 THEN '两融标的' END,
        CASE WHEN COALESCE(sdl_run.idx_all, 0) <> 0 THEN '全市场' END
      ]::text[], NULL)),
      '[]'::jsonb
    ) AS index_tags,
    COALESCE(sdl_run.trade_date, '1970-01-01') AS latest_trade_date,
    COALESCE(sdl_run.consecutive_limit_up_days, 0) AS consecutive_limit_up_days_sdl
"""


_SDL_LATEST = """
    SELECT DISTINCT ON (symbol) symbol, trade_date, stock_name, industry,
        close, pct_change, pe_ttm, pb, roe, adj_factor, turnover_rate, amount, total_mv, float_mv, listed_days, is_st,
        idx_hs300, idx_zz1000, idx_chinext, idx_margin, idx_all,
        ma5, ma10, ma_gap_5, ma_gap_10, ma_gap_20,
        rsi_14, rsi_6, vol_atr_14, macd_hist, volume_ratio_5, volume_ratio_20, volume_trend_3d,
        main_flow, flow_net_amount, inst_ownership, profit_growth,
        concept_ai, concept_chip, concept_new_energy, concept_pv, concept_lithium, concept_military,
        concept_medical, concept_fintech, concept_consumption, concept_state_owned,
        consecutive_limit_up_days
    FROM stock_daily_latest
    WHERE volume > 0
    ORDER BY symbol, trade_date DESC
"""

_SDL_SELECT_SIMPLE = """
    COALESCE(sdl_latest.stock_name, '') AS stock_name,
    COALESCE(sdl_latest.industry, '') AS industry,
    COALESCE(sdl_latest.close, 0) AS close_price,
    COALESCE(sdl_latest.pe_ttm, 0) AS pe,
    COALESCE(sdl_latest.pb, 0) AS pb,
    COALESCE(sdl_latest.roe, 0) AS roe,
    COALESCE(sdl_latest.turnover_rate, 0) * 100 AS turnover_rate,
    COALESCE(sdl_latest.amount, 0) AS amount,
    COALESCE(sdl_latest.total_mv, 0) AS total_mv,
    COALESCE(sdl_latest.float_mv, 0) AS float_mv,
    COALESCE(sdl_latest.listed_days, 0) AS listed_days,
    COALESCE(sdl_latest.is_st, 0) <> 0 AS is_st,
    COALESCE(sdl_latest.idx_hs300, 0) <> 0 AS is_hs300,
    0 <> 0 AS is_csi500,
    COALESCE(sdl_latest.idx_zz1000, 0) <> 0 AS is_csi1000,
    COALESCE(sdl_latest.pct_change, 0) AS latest_change_pct,
    0 AS return_1d,
    0 AS return_3d,
    COALESCE(sdl_latest.ma5, 0) AS ma5,
    COALESCE(sdl_latest.ma10, 0) AS ma10,
    COALESCE(sdl_latest.ma_gap_5, 0) AS ma_gap_5,
    COALESCE(sdl_latest.ma_gap_10, 0) AS ma_gap_10,
    COALESCE(sdl_latest.ma_gap_20, 0) AS ma_gap_20,
    COALESCE(sdl_latest.rsi_14, sdl_latest.rsi_6, 0) AS rsi,
    COALESCE(sdl_latest.rsi_14, 0) AS rsi_14,
    COALESCE(sdl_latest.vol_atr_14, 0) AS atr,
    COALESCE(sdl_latest.macd_hist, 0) AS macd_hist,
    COALESCE(sdl_latest.volume_ratio_5, 0) AS volume_ratio_5,
    COALESCE(sdl_latest.volume_ratio_20, 0) AS volume_ratio_20,
    CASE WHEN COALESCE(sdl_latest.volume_trend_3d, false) THEN 1 ELSE 0 END AS volume_trend_3d,
    COALESCE(sdl_latest.main_flow, 0) AS main_flow,
    COALESCE(sdl_latest.flow_net_amount, 0) AS flow_net_amount,
    COALESCE(sdl_latest.inst_ownership, 0) AS inst_ownership,
    COALESCE(sdl_latest.profit_growth, 0) AS profit_growth,
    COALESCE(
      (
        SELECT to_jsonb(array_agg(tag))
        FROM (
          SELECT tag
          FROM (
            VALUES
              ('AI', COALESCE(sdl_latest.concept_ai, 0)),
              ('芯片', COALESCE(sdl_latest.concept_chip, 0)),
              ('新能源', COALESCE(sdl_latest.concept_new_energy, 0)),
              ('光伏', COALESCE(sdl_latest.concept_pv, 0)),
              ('锂电', COALESCE(sdl_latest.concept_lithium, 0)),
              ('军工', COALESCE(sdl_latest.concept_military, 0)),
              ('医药', COALESCE(sdl_latest.concept_medical, 0)),
              ('金融科技', COALESCE(sdl_latest.concept_fintech, 0)),
              ('消费', COALESCE(sdl_latest.concept_consumption, 0)),
              ('国企改革', COALESCE(sdl_latest.concept_state_owned, 0))
          ) AS concept_scores(tag, score)
          WHERE score > 0
          ORDER BY score DESC
          LIMIT 3
        ) ranked_tags
      ),
      '[]'::jsonb
    ) AS concept_tags,
    COALESCE(
      to_jsonb(array_remove(ARRAY[
        CASE WHEN COALESCE(sdl_latest.idx_hs300, 0) <> 0 THEN '沪深300' END,
        CASE WHEN 0 <> 0 THEN '中证500' END,
        CASE WHEN COALESCE(sdl_latest.idx_zz1000, 0) <> 0 THEN '中证1000' END,
        CASE WHEN COALESCE(sdl_latest.idx_chinext, 0) <> 0 THEN '创业板指数' END,
        CASE WHEN COALESCE(sdl_latest.idx_margin, 0) <> 0 THEN '两融标的' END,
        CASE WHEN COALESCE(sdl_latest.idx_all, 0) <> 0 THEN '全市场' END
      ]::text[], NULL)),
      '[]'::jsonb
    ) AS index_tags,
    sdl_latest.trade_date AS latest_trade_date,
    COALESCE(sdl_latest.consecutive_limit_up_days, 0) AS consecutive_limit_up_days_sdl,
    COALESCE(sdl_latest.adj_factor, 1) AS adj_factor
"""


def _sdl_join_condition(symbol_expr: str = "snap.symbol") -> str:
    return f"(\n    sdl_latest.symbol = {_norm_symbol_sql(symbol_expr)}\n)"


def _serialize_date(d: Any) -> str | None:
    return d.isoformat() if isinstance(d, (date, datetime)) else None


def _serialize_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        val = float(v)
        if math.isfinite(val):
            return val
        return None
    except (ValueError, TypeError):
        return None


def _serialize_int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except Exception:
        return None


def _to_nominal_price(numeric_price: Any, adj_factor: Any) -> float:
    numeric_price = _serialize_float(numeric_price) or 0.0
    numeric_adj_factor = _serialize_float(adj_factor) or 1.0
    return round(numeric_price / numeric_adj_factor, 2)


def _resolve_stock_name(row, symbol):
    # Try all possible name fields from DB
    for field in ["stock_name", "name"]:
        val = row.get(field)
        if val and val != symbol:
            return val
    # For crypto symbols like BTCUSDT, extract base asset
    sym = str(symbol or "").upper()
    if sym.endswith("USDT"):
        return sym[:-4]
    if sym.endswith("BUSD") or sym.endswith("USD"):
        return sym[:-4]
    return symbol


def _format_candidate_record(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "unknown")
    run_id = str(row.get("run_id") or "unknown")
    stock_name = _resolve_stock_name(row, symbol)

    def to_yi(v):
        val = _serialize_float(v) or 0.0
        return val / 100000000.0

    def parse_json(v):
        if not v:
            return []
        if isinstance(v, (list, dict)):
            return v
        try:
            return json.loads(v)
        except Exception:
            return []

    concept_tags = parse_json(row.get("concept_tags"))
    index_tags = parse_json(row.get("index_tags"))
    risk_flags = parse_json(row.get("risk_flags"))
    return_1d = _serialize_float(row.get("return_1d"))
    return_3d = _serialize_float(row.get("return_3d"))
    latest_change_pct = _serialize_float(row.get("latest_change_pct")) or 0.0

    snapshot_turnover_rate = _serialize_float(row.get("snapshot_turnover_rate"))
    live_turnover_rate = _serialize_float(row.get("turnover_rate") or 0.0) or 0.0
    resolved_turnover_rate = snapshot_turnover_rate if snapshot_turnover_rate is not None else live_turnover_rate

    def _safe(v, default=0.0):
        """Return None for NULL DB values so frontend can display '-' instead of 0."""
        sv = _serialize_float(v)
        return sv if sv is not None else None

    def _safe_int(v, default=0):
        sv = _serialize_int(v)
        return sv if sv is not None else None

    close_price_raw = _serialize_float(row.get("close_price"))
    adj_factor_raw = _serialize_float(row.get("adj_factor")) or 1.0
    total_mv_raw = _serialize_float(row.get("total_mv"))
    float_mv_raw = _serialize_float(row.get("float_mv"))
    amount_raw = _serialize_float(row.get("amount"))
    turnover_raw = _serialize_float(row.get("turnover_rate"))
    pe_raw = _serialize_float(row.get("pe"))
    roe_raw = _serialize_float(row.get("roe"))
    rsi_raw = _serialize_float(row.get("rsi"))
    rsi14_raw = _serialize_float(row.get("rsi_14"))
    atr_raw = _serialize_float(row.get("atr"))
    macd_raw = _serialize_float(row.get("macd_hist"))
    ma_gap_5_raw = _serialize_float(row.get("ma_gap_5"))
    ma_gap_10_raw = _serialize_float(row.get("ma_gap_10"))
    ma_gap_20_raw = _serialize_float(row.get("ma_gap_20"))
    vol_ratio_5_raw = _serialize_float(row.get("volume_ratio_5"))
    vol_ratio_20_raw = _serialize_float(row.get("volume_ratio_20"))
    main_flow_raw = _serialize_float(row.get("main_flow"))
    flow_net_raw = _serialize_float(row.get("flow_net_amount"))
    inst_own_raw = _serialize_float(row.get("inst_ownership"))
    profit_growth_raw = _serialize_float(row.get("profit_growth"))
    ma5_raw = _serialize_float(row.get("ma5"))
    ma10_raw = _serialize_float(row.get("ma10"))
    listed_days_raw = _serialize_int(row.get("listed_days"))
    consecutive_lu_raw = _serialize_int(row.get("consecutive_limit_up_days")) or _serialize_int(row.get("consecutive_limit_up_days_sdl"))

    return {
        "key": f"{run_id}:{symbol}",
        "modelId": row.get("model_id"),
        "runId": run_id,
        "rank": _serialize_int(row.get("score_rank")) or 0,
        "code": symbol,
        "name": stock_name,
        "score": _serialize_float(row.get("fusion_score")) or 0.0,
        "latestChange": latest_change_pct,
        "consecutiveLimitUpDays": consecutive_lu_raw if consecutive_lu_raw is not None else 0,
        "turnoverRate": round(turnover_raw, 2) if turnover_raw is not None else None,
        "amount": round(to_yi(amount_raw), 4) if amount_raw is not None else None,
        "marketCap": round(to_yi(total_mv_raw), 2) if total_mv_raw is not None else None,
        "totalMv": round(to_yi(total_mv_raw), 2) if total_mv_raw is not None else None,
        "floatMv": round(to_yi(float_mv_raw), 2) if float_mv_raw is not None else None,
        "listedDays": listed_days_raw,
        "sector": row.get("industry") or "",
        "concept": " / ".join(concept_tags[:3]) if isinstance(concept_tags, list) and concept_tags else "",
        "conceptTags": concept_tags if isinstance(concept_tags, list) else [],
        "indexTags": index_tags if isinstance(index_tags, list) else [],
        "riskFlags": risk_flags if isinstance(risk_flags, list) else [],
        "closePrice": _to_nominal_price(close_price_raw, adj_factor_raw),
        "pe": round(pe_raw, 2) if pe_raw is not None else None,
        "pb": round(_serialize_float(row.get("pb")) or 0.0, 2),
        "roe": round(roe_raw, 2) if roe_raw is not None else None,
        "ma5": round(ma5_raw / adj_factor_raw, 2) if ma5_raw is not None else None,
        "ma10": round(ma10_raw / adj_factor_raw, 2) if ma10_raw is not None else None,
        "maGap5": round(ma_gap_5_raw, 2) if ma_gap_5_raw is not None else None,
        "maGap10": round(ma_gap_10_raw, 2) if ma_gap_10_raw is not None else None,
        "maGap20": round(ma_gap_20_raw, 2) if ma_gap_20_raw is not None else None,
        "rsi": round(rsi_raw, 1) if rsi_raw is not None else None,
        "rsi14": round(rsi14_raw, 1) if rsi14_raw is not None else None,
        "atr": round(atr_raw, 3) if atr_raw is not None else None,
        "macdHist": round(macd_raw, 3) if macd_raw is not None else None,
        "volRatio5": round(vol_ratio_5_raw, 2) if vol_ratio_5_raw is not None else None,
        "volRatio20": round(vol_ratio_20_raw, 2) if vol_ratio_20_raw is not None else None,
        "volumeTrend3d": _serialize_float(row.get("volume_trend_3d")),
        "volumeTrend5d": False,
        "return1d": return_1d,
        "return3d": return_3d,
        "nextDayReturn": return_1d,
        "day3Return": return_3d,
        "mainFlow": round(main_flow_raw / 1000000.0, 2) if main_flow_raw is not None else None,
        "flowNetAmount": round(flow_net_raw / 1000000.0, 2) if flow_net_raw is not None else None,
        "instOwnership": round(inst_own_raw / 1000000.0, 2) if inst_own_raw is not None else None,
        "profitGrowth": round(profit_growth_raw, 2) if profit_growth_raw is not None else None,
        "isSt": bool(row.get("is_st")),
        "isTradable": close_price_raw is not None and close_price_raw > 0,
        "thesis": row.get("thesis_summary") or "",
        "updatedAt": _serialize_date(row.get("updated_at")),
        "isHs300": bool(row.get("is_hs300")),
        "isCsi500": bool(row.get("is_csi500")),
        "isCsi1000": bool(row.get("is_csi1000")),
    }


async def _fetch_summary(
    session, where: str, params: dict[str, Any], include_market_stats: bool = True, market: str | None = None
) -> dict[str, Any]:
    if include_market_stats:
        sdl_tbl = _get_sdl_table(market)
        summary_sql = f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE (sdl.close > 0)) AS tradable_count,
                COUNT(*) FILTER (WHERE (sdl.idx_hs300 <> 0)) AS hs300_count,
                COUNT(*) FILTER (WHERE (sdl.idx_zz1000 <> 0)) AS zz1000_count,
                COUNT(*) FILTER (WHERE (sdl.idx_margin <> 0)) AS margin_count,
                COUNT(*) FILTER (WHERE (sdl.idx_chinext <> 0)) AS chinext_count,
                AVG(COALESCE(snap.fusion_score, 0)) AS avg_score,
                COUNT(*) FILTER (WHERE COALESCE(snap.confidence_level, 'watch') = 'high') AS high_confidence_count,
                COUNT(*) FILTER (WHERE COALESCE(snap.fusion_score, 0) >= 0.05) AS strong_count,
                MAX(snap.updated_at) AS last_updated_at
            FROM qm_research_candidate_snapshot snap
            LEFT JOIN {sdl_tbl} sdl ON (
                sdl.symbol = {_norm_symbol_sql("snap.symbol")}
                AND sdl.trade_date = snap.data_trade_date
            )
            WHERE {where}
        """
    else:
        summary_sql = f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) AS tradable_count,
                0 AS hs300_count,
                0 AS zz1000_count,
                0 AS margin_count,
                0 AS chinext_count,
                AVG(COALESCE(snap.fusion_score, 0)) AS avg_score,
                COUNT(*) FILTER (WHERE COALESCE(snap.confidence_level, 'watch') = 'high') AS high_confidence_count,
                COUNT(*) FILTER (WHERE COALESCE(snap.fusion_score, 0) >= 0.05) AS strong_count,
                MAX(snap.updated_at) AS last_updated_at
            FROM qm_research_candidate_snapshot snap
            WHERE {where}
        """

    result = await session.execute(text(summary_sql), params)
    row = result.mappings().first()
    if row is None:
        return {
            "total": 0,
            "totalMarket": 0,
            "hs300": 0,
            "zz1000": 0,
            "margin": 0,
            "chinext": 0,
            "avgScore": 0.0,
            "highConfidenceCount": 0,
            "strongCount": 0,
            "lastUpdatedAt": None,
        }
    payload = dict(row)
    return {
        "total": _serialize_int(payload.get("total_count")) or 0,
        "totalMarket": _serialize_int(payload.get("tradable_count")) or 0,
        "hs300": _serialize_int(payload.get("hs300_count")) or 0,
        "zz1000": _serialize_int(payload.get("zz1000_count")) or 0,
        "margin": _serialize_int(payload.get("margin_count")) or 0,
        "chinext": _serialize_int(payload.get("chinext_count")) or 0,
        "avgScore": round(_serialize_float(payload.get("avg_score")) or 0.0, 4),
        "highConfidenceCount": _serialize_int(payload.get("high_confidence_count")) or 0,
        "strongCount": _serialize_int(payload.get("strong_count")) or 0,
        "lastUpdatedAt": _serialize_date(payload.get("last_updated_at")),
    }


async def _do_get_overview(
    tid: str,
    uid: str,
    model_id: str | None,
    run_id: str | None,
    limit: int,
    offset: int,
    include_market_stats: bool = True,
    market: str | None = None,
) -> dict[str, Any]:
    where = "snap.tenant_id = :tid AND snap.user_id = :uid"
    params = {"tid": tid, "uid": uid, "limit": limit, "offset": offset}
    if model_id:
        where += " AND snap.model_id = :mid"
        params["mid"] = model_id
    if run_id:
        where += " AND snap.run_id = :rid"
        params["rid"] = run_id

    sdl_table = _get_sdl_table(market)
    is_cn = not market or market.upper() == "CN"

    async with get_session(read_only=True) as session:
        # Non-CN tables have simpler schema — use lightweight SDL columns
        if is_cn:
            sdl_columns = """
                sdl.stock_name, sdl.industry, sdl.close, sdl.pct_change,
                sdl.pe_ttm, sdl.pb, sdl.roe, sdl.adj_factor,
                sdl.turnover_rate, sdl.amount, sdl.total_mv, sdl.float_mv,
                sdl.listed_days, sdl.is_st,
                sdl.idx_hs300, 0 AS idx_zz500, sdl.idx_zz1000,
                sdl.idx_chinext, sdl.idx_margin, sdl.idx_all,
                sdl.ma5, sdl.ma10, sdl.ma_gap_5, sdl.ma_gap_10, sdl.ma_gap_20,
                sdl.rsi_14, sdl.rsi_6, sdl.vol_atr_14, sdl.macd_hist,
                sdl.volume_ratio_5, sdl.volume_ratio_20, sdl.volume_trend_3d,
                sdl.main_flow, sdl.flow_net_amount, sdl.inst_ownership,
                sdl.profit_growth,
                sdl.concept_ai, sdl.concept_chip, sdl.concept_new_energy,
                sdl.concept_pv, sdl.concept_lithium, sdl.concept_military,
                sdl.concept_medical, sdl.concept_fintech, sdl.concept_consumption,
                sdl.concept_state_owned, sdl.consecutive_limit_up_days,
            """
        else:
            sdl_columns = """
                sdl.name AS stock_name, sdl.industry, sdl.close, COALESCE(sdl.pct_change, 0) AS pct_change,
                sdl.pe_ttm, sdl.pb, sdl.roe, sdl.adj_factor,
                sdl.turnover_rate, sdl.amount, sdl.total_mv, sdl.float_mv,
                0 AS listed_days, 0 AS is_st,
                0 AS idx_hs300, 0 AS idx_zz500, 0 AS idx_zz1000,
                0 AS idx_chinext, 0 AS idx_margin, 0 AS idx_all,
                sdl.ma5, sdl.ma10, sdl.ma_gap_5, sdl.ma_gap_10, sdl.ma_gap_20,
                sdl.rsi_14, sdl.rsi_6, sdl.vol_atr_14, sdl.macd_hist,
                sdl.volume_ratio_5, sdl.volume_ratio_20, 0 AS volume_trend_3d,
                0 AS main_flow, sdl.flow_net_amount, 0 AS inst_ownership,
                0 AS profit_growth,
                0 AS concept_ai, 0 AS concept_chip, 0 AS concept_new_energy,
                0 AS concept_pv, 0 AS concept_lithium, 0 AS concept_military,
                0 AS concept_medical, 0 AS concept_fintech, 0 AS concept_consumption,
                0 AS concept_state_owned, 0 AS consecutive_limit_up_days,
            """

        sql = f"""
        WITH snap_page AS (
            SELECT snap.*
            FROM qm_research_candidate_snapshot snap
            WHERE {where}
            ORDER BY snap.score_rank ASC
            LIMIT :limit OFFSET :offset
        ),
        snap_symbols AS (
            SELECT DISTINCT snap.symbol AS symbol
            FROM snap_page snap
        ),
        snap_date_bounds AS (
            SELECT
                MIN(snap.data_trade_date) AS min_trade_date,
                MAX(snap.data_trade_date) AS max_trade_date
            FROM snap_page snap
        ),
        sdl_run AS (
            SELECT
                sdl.symbol,
                sdl.trade_date,
                {sdl_columns}
                CASE
                    WHEN LAG(sdl.volume, 3) OVER (PARTITION BY sdl.symbol ORDER BY sdl.trade_date) > 0
                    THEN (sdl.volume::double precision - LAG(sdl.volume, 3) OVER (PARTITION BY sdl.symbol ORDER BY sdl.trade_date)::double precision)
                         / LAG(sdl.volume, 3) OVER (PARTITION BY sdl.symbol ORDER BY sdl.trade_date)::double precision
                    ELSE NULL
                END AS volume_trend_3d_calc,
                LEAD(sdl.close, 1) OVER (PARTITION BY sdl.symbol ORDER BY sdl.trade_date) AS close_next_1d,
                LEAD(sdl.close, 3) OVER (PARTITION BY sdl.symbol ORDER BY sdl.trade_date) AS close_next_3d
            FROM {sdl_table} sdl
            INNER JOIN snap_symbols ss ON ss.symbol = sdl.symbol
            CROSS JOIN snap_date_bounds b
            WHERE sdl.volume > 0
              AND sdl.trade_date >= (b.min_trade_date - INTERVAL '10 day')
              AND sdl.trade_date <= (b.max_trade_date + INTERVAL '20 day')
        )
        SELECT snap.*, {_SDL_SELECT_BY_RUN_DATE}
        FROM snap_page snap
        LEFT JOIN sdl_run
            ON sdl_run.symbol = {_norm_symbol_sql("snap.symbol")}
           AND sdl_run.trade_date = snap.data_trade_date
        ORDER BY snap.score_rank ASC
        """
        result = await session.execute(text(sql), params)
        items = [_format_candidate_record(dict(r)) for r in result.mappings()]
        summary = await _fetch_summary(session, where, params, include_market_stats=include_market_stats and is_cn, market=market)
    return {"items": items, "summary": summary}


def _humanize_model_name(model_id: str) -> str:
    if not model_id:
        return "Unknown Model"
    if model_id == "alpha158":
        return "Alpha158 (Baseline)"
    if model_id == "model_qlib":
        return "Qlib LightGBM"
    if model_id.startswith("mdl_train_"):
        parts = model_id.split("_")
        if len(parts) >= 3:
            ts = parts[2]
            if len(ts) >= 12:
                try:
                    dt = datetime.strptime(ts[:12], "%Y%m%d%H%M")
                    return f"训练模型 ({dt.strftime('%m/%d %H:%M')})"
                except Exception:
                    pass
    return model_id.replace("_", " ").title()


async def get_available_models(tid: str, uid: str, market: str | None = None) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        # Build market filter condition for metadata_json
        market_filter = ""
        params: dict[str, Any] = {"tid": tid, "uid": uid}
        if market:
            # metadata_json->'context'->>'market' stores the training market
            market_upper = market.upper()
            market_filter = "AND COALESCE(um.metadata_json->'context'->>'market', 'CN') = :market"
            params["market"] = market_upper

        sql = (
            "SELECT model_id, display_name FROM ("
            # Models with completed inference runs + research snapshots
            "  SELECT DISTINCT ir.model_id,"
            "         COALESCE(um.metadata_json->>'display_name', um.metadata_json->>'model_name') AS display_name,"
            "         1 AS priority"
            "  FROM qm_model_inference_runs ir"
            "  INNER JOIN qm_research_candidate_snapshot snap ON snap.tenant_id = ir.tenant_id"
            "                                                  AND snap.user_id = ir.user_id"
            "                                                  AND snap.model_id = ir.model_id"
            "  LEFT JOIN qm_user_models um ON um.tenant_id = ir.tenant_id"
            "                              AND um.user_id = ir.user_id"
            "                              AND um.model_id = ir.model_id"
            "  WHERE ir.tenant_id = :tid AND ir.user_id = :uid AND ir.status = 'completed'"
            f"  {market_filter}"
            "  UNION"
            # All trained models (even without inference runs)
            "  SELECT um.model_id,"
            "         COALESCE(um.metadata_json->>'display_name', um.metadata_json->>'model_name') AS display_name,"
            "         2 AS priority"
            "  FROM qm_user_models um"
            "  WHERE um.tenant_id = :tid AND um.user_id = :uid AND um.status != 'archived'"
            f"  {market_filter}"
            ") combined"
            " ORDER BY priority, display_name"
        )
        res = await session.execute(text(sql), params)
        seen = set()
        models = []
        for r in res.mappings():
            mid = r["model_id"]
            if mid in seen:
                continue
            seen.add(mid)
            name = r["display_name"] or _humanize_model_name(mid)
            models.append({"modelId": mid, "name": name})
        return {"code": 200, "data": {"models": models}}


async def get_inference_runs(tid: str, uid: str, model_id: str) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        res = await session.execute(
            text(
                """
                SELECT run_id, data_trade_date, prediction_trade_date, status, updated_at
                FROM qm_model_inference_runs
                WHERE tenant_id = :tid AND user_id = :uid AND model_id = :mid
                ORDER BY prediction_trade_date DESC, created_at DESC
                """
            ),
            {"tid": tid, "uid": uid, "mid": model_id},
        )
        return {
            "code": 200,
            "data": {
                "runs": [
                    {
                        "runId": r[0],
                        "modelId": model_id,
                        "inferenceDate": _serialize_date(r[1]),
                        "targetDate": _serialize_date(r[2]),
                        "status": str(r[3] or "completed"),
                        "lastUpdatedAt": _serialize_date(r[4]),
                        "universeLabel": "",
                    }
                    for r in res
                ]
            },
        }


async def get_research_overview(
    tid: str, uid: str, model_id: str | None, run_id: str | None, limit: int, offset: int, market: str | None = None
) -> dict[str, Any]:
    data = await _do_get_overview(tid, uid, model_id, run_id, limit, offset, market=market)
    return {"code": 200, "data": {"items": data["items"], "summary": data["summary"]}}


async def _do_get_universe_with_sdl_redis(
    tid: str, uid: str, run_id: str, limit: int, offset: int, market: str | None = None
) -> dict[str, Any] | None:
    params = {"tid": tid, "uid": uid, "rid": run_id, "limit": limit, "offset": offset}
    where = "snap.tenant_id = :tid AND snap.user_id = :uid AND snap.run_id = :rid"
    async with get_session(read_only=True) as session:
        snap_sql = f"""
            SELECT snap.*
            FROM qm_research_candidate_snapshot snap
            WHERE {where}
            ORDER BY snap.score_rank ASC
            LIMIT :limit OFFSET :offset
        """
        snap_rows = (await session.execute(text(snap_sql), params)).mappings().all()
        if not snap_rows:
            summary = await _fetch_summary(session, where, params, include_market_stats=False)
            return {"items": [], "summary": summary}

        trade_dates = {row.get("data_trade_date") for row in snap_rows}
        if len(trade_dates) != 1:
            return None
        trade_date = next(iter(trade_dates))
        if not isinstance(trade_date, date) or trade_date.year != _SDL_REDIS_YEAR:
            return None

        sdl_map = await _load_sdl_day_map(session, trade_date, market=market)
        if not sdl_map:
            return None

        merged_rows: list[dict[str, Any]] = []
        for row in snap_rows:
            snap = dict(row)
            symbol = StockCodeUtil.to_prefix(str(snap.get("symbol") or ""))
            merged = dict(snap)
            sdl = sdl_map.get(symbol)
            if sdl:
                merged.update(sdl)
            merged_rows.append(merged)

        items = [_format_candidate_record(r) for r in merged_rows]
        summary = await _fetch_summary(session, where, params, include_market_stats=False)
        return {"items": items, "summary": summary}


async def _infer_market_from_run(tid: str, uid: str, run_id: str) -> str | None:
    """Infer market from an inference run's model metadata."""
    try:
        async with get_session(read_only=True) as session:
            res = await session.execute(
                text(
                    "SELECT ir.model_id FROM qm_model_inference_runs ir "
                    "WHERE ir.tenant_id = :tid AND ir.user_id = :uid AND ir.run_id = :rid"
                ),
                {"tid": tid, "uid": uid, "rid": run_id},
            )
            row = res.first()
            if not row:
                return None
            model_id = row[0]
            # Look up model metadata
            res2 = await session.execute(
                text(
                    "SELECT metadata_json FROM qm_user_models "
                    "WHERE tenant_id = :tid AND user_id = :uid AND model_id = :mid"
                ),
                {"tid": tid, "uid": uid, "mid": model_id},
            )
            row2 = res2.first()
            if row2 and row2[0]:
                meta = row2[0] if isinstance(row2[0], dict) else json.loads(row2[0])
                context = meta.get("context")
                if isinstance(context, dict):
                    market = str(context.get("market", "")).upper()
                    if market in ("CN", "HK", "US", "CRYPTO"):
                        return market
    except Exception:
        pass
    return None


async def get_research_universe(tid: str, uid: str, run_id: str, limit: int, offset: int = 0) -> dict[str, Any]:
    cache_key = f"{tid}:{uid}:{run_id}:{limit}:{offset}"
    cached = _get_local_cache(_UNIVERSE_CACHE, cache_key, _UNIVERSE_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    # Determine market from the inference run's model
    market = await _infer_market_from_run(tid, uid, run_id)

    data = await _do_get_universe_with_sdl_redis(tid, uid, run_id, limit, offset, market=market)
    if data is None:
        data = await _do_get_overview(tid, uid, None, run_id, limit, offset, include_market_stats=False, market=market)
    payload = {"code": 200, "data": {"items": data["items"], "summary": data["summary"]}}
    _set_local_cache(_UNIVERSE_CACHE, cache_key, payload, _UNIVERSE_CACHE_MAX_ENTRIES)
    return payload


async def get_user_watchlist(tid: str, uid: str, limit: int, offset: int) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        res = await session.execute(
            text(
                "SELECT symbol, stock_name, added_at, source_run_id FROM qm_user_watchlist "
                "WHERE tenant_id = :tid AND user_id = :uid ORDER BY added_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"tid": tid, "uid": uid, "limit": limit, "offset": offset},
        )
        items = [
            {"symbol": r[0], "stockName": r[1], "addedAt": _serialize_date(r[2]), "sourceRunId": r[3]} for r in res
        ]
        total = (
            await session.execute(
                text("SELECT COUNT(*) FROM qm_user_watchlist WHERE tenant_id = :tid AND user_id = :uid"),
                {"tid": tid, "uid": uid},
            )
        ).scalar() or 0
    return {"code": 200, "data": {"items": items, "total": total}}


async def add_to_watchlist(
    tid: str, uid: str, symbol: str, run_id: str | None, stock_name: str | None, features_snapshot: dict[str, Any] | None
) -> dict[str, Any]:
    async with get_session() as session:
        await session.execute(
            text(
                "INSERT INTO qm_user_watchlist (tenant_id, user_id, symbol, stock_name, source_run_id, features_snapshot, updated_at) "
                "VALUES (:tid, :uid, :s, :n, :rid, :f, NOW()) "
                "ON CONFLICT (tenant_id, user_id, symbol) DO UPDATE SET features_snapshot = EXCLUDED.features_snapshot, updated_at = NOW()"
            ),
            {"tid": tid, "uid": uid, "s": symbol, "n": stock_name, "rid": run_id, "f": json.dumps(features_snapshot or {})},
        )
    return {"code": 200, "message": "success"}


async def remove_from_watchlist(tid: str, uid: str, symbol: str) -> dict[str, Any]:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM qm_user_watchlist WHERE tenant_id = :tid AND user_id = :uid AND symbol = :s"),
            {"tid": tid, "uid": uid, "s": symbol},
        )
    return {"code": 200, "message": "success"}


async def get_user_research_pool(tid: str, uid: str, status: str | None, limit: int, offset: int) -> dict[str, Any]:
    where = "tenant_id = :tid AND user_id = :uid"
    params: dict[str, Any] = {"tid": tid, "uid": uid, "limit": limit, "offset": offset}
    if status:
        where += " AND status = :status"
        params["status"] = status
    async with get_session(read_only=True) as session:
        res = await session.execute(
            text(
                f"SELECT symbol, stock_name, added_at, source_run_id, status FROM qm_user_research_pool "
                f"WHERE {where} ORDER BY added_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        items = [
            {"symbol": r[0], "stockName": r[1], "addedAt": _serialize_date(r[2]), "sourceRunId": r[3], "status": r[4]}
            for r in res
        ]
        total = (await session.execute(text(f"SELECT COUNT(*) FROM qm_user_research_pool WHERE {where}"), params)).scalar() or 0
    return {"code": 200, "data": {"items": items, "total": total}}


async def add_to_research_pool(
    tid: str,
    uid: str,
    symbol: str,
    run_id: str | None,
    stock_name: str | None,
    model_id: str | None,
    fusion_score: float | None,
    thesis_summary: str | None,
    features_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    async with get_session() as session:
        await session.execute(
            text(
                "INSERT INTO qm_user_research_pool "
                "(tenant_id, user_id, symbol, stock_name, source_run_id, model_id, fusion_score, thesis_summary, features_snapshot, updated_at) "
                "(VALUES (:tid, :uid, :s, :n, :rid, :mid, :fs, :ts, :f, NOW())) "
                "ON CONFLICT (tenant_id, user_id, symbol) DO UPDATE SET features_snapshot = EXCLUDED.features_snapshot, updated_at = NOW()"
            ),
            {
                "tid": tid,
                "uid": uid,
                "s": symbol,
                "n": stock_name,
                "rid": run_id,
                "mid": model_id,
                "fs": fusion_score,
                "ts": thesis_summary,
                "f": json.dumps(features_snapshot or {}),
            },
        )
    return {"code": 200, "message": "success"}


async def remove_from_research_pool(tid: str, uid: str, symbol: str) -> dict[str, Any]:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM qm_user_research_pool WHERE tenant_id = :tid AND user_id = :uid AND symbol = :s"),
            {"tid": tid, "uid": uid, "s": symbol},
        )
    return {"code": 200, "message": "success"}


async def get_symbols_features(tid: str, uid: str, symbols: list[str], lite: bool) -> dict[str, Any]:
    normalized_symbols = [StockCodeUtil.to_prefix(s.strip()) for s in symbols if s.strip()]
    if not normalized_symbols:
        return {"code": 200, "data": {"items": []}}

    vals = ", ".join(f"('{s}')" for s in normalized_symbols)
    norm = _norm_symbol_sql("symbol")

    # 简化逻辑：直接读取数据库中的快照，不再进行实时关联或计算
    sql = f"""
        WITH sym_list(raw_symbol) AS (VALUES {vals}),
        pool_norm AS (
            SELECT symbol, features_snapshot, ({norm}) AS prefix_symbol
            FROM qm_user_research_pool WHERE tenant_id = :tid AND user_id = :uid
        ),
        watchlist_norm AS (
            SELECT symbol, features_snapshot, ({norm}) AS prefix_symbol
            FROM qm_user_watchlist WHERE tenant_id = :tid AND user_id = :uid
        )
        SELECT
            sym_list.raw_symbol AS symbol,
            COALESCE(ps.features_snapshot, ws.features_snapshot) as snapshot
        FROM sym_list
        LEFT JOIN pool_norm ps ON ps.prefix_symbol = sym_list.raw_symbol
        LEFT JOIN watchlist_norm ws ON ws.prefix_symbol = sym_list.raw_symbol
    """
    async with get_session(read_only=True) as session:
        result = await session.execute(text(sql), {"tid": tid, "uid": uid})
        items = []
        missing_symbols = []
        for r in result.mappings():
            snap = r["snapshot"]
            if not snap:
                missing_symbols.append(r["symbol"])
                continue
            if isinstance(snap, str):
                try:
                    snap = json.loads(snap)
                except Exception:
                    missing_symbols.append(r["symbol"])
                    continue
            # 确保 symbol 一致
            snap["code"] = r["symbol"]
            items.append(snap)

        # 对于没有 features_snapshot 的股票，从 stock_daily_latest 补充基础数据
        if missing_symbols:
            sdl_vals = ", ".join(f"('{s}')" for s in missing_symbols)
            sdl_norm = _norm_symbol_sql("sdl.symbol")
            sdl_sql = f"""
                WITH miss(raw_symbol) AS (VALUES {sdl_vals}),
                ranked AS (
                    SELECT
                        miss.raw_symbol AS raw_symbol,
                        sdl.stock_name,
                        sdl.industry,
                        sdl.close,
                        sdl.pe_ttm,
                        sdl.pb,
                        sdl.roe,
                        sdl.total_mv,
                        sdl.float_mv,
                        sdl.pct_change,
                        sdl.turnover_rate,
                        sdl.amount,
                        ROW_NUMBER() OVER (PARTITION BY miss.raw_symbol ORDER BY sdl.trade_date DESC) AS rn
                    FROM miss
                    LEFT JOIN stock_daily_latest sdl ON ({sdl_norm}) = miss.raw_symbol
                )
                SELECT raw_symbol, stock_name, industry, close, pe_ttm, pb, roe,
                       total_mv, float_mv, pct_change, turnover_rate, amount
                FROM ranked WHERE rn = 1
            """
            sdl_result = await session.execute(text(sdl_sql))
            for r in sdl_result.mappings():
                raw_sym = r["raw_symbol"]
                stock_name = r.get("stock_name") or raw_sym
                close_price = float(r.get("close") or 0)
                total_mv = float(r.get("total_mv") or 0)
                pe_val = float(r.get("pe_ttm") or 0)
                snap = {
                    "code": raw_sym,
                    "name": stock_name,
                    "marketCap": round(total_mv / 1e8, 2) if total_mv else 0,
                    "totalMv": round(total_mv / 1e8, 2) if total_mv else 0,
                    "pe": pe_val,
                    "pe_ttm": pe_val,
                    "pb": float(r.get("pb") or 0),
                    "roe": float(r.get("roe") or 0),
                    "closePrice": close_price,
                    "price": close_price,
                    "sector": r.get("industry") or "",
                    "industry": r.get("industry") or "",
                    "latestChange": float(r.get("pct_change") or 0),
                    "turnoverRate": float(r.get("turnover_rate") or 0) * 100,
                    "amount": float(r.get("amount") or 0),
                    "floatMv": round(float(r.get("float_mv") or 0) / 1e8, 2) if r.get("float_mv") else 0,
                }
                items.append(snap)

        return {"code": 200, "data": {"items": items}}


async def get_stock_kline(symbol: str, days: int) -> dict[str, Any]:
    normalized_symbol = StockCodeUtil.to_prefix(symbol)
    cache_key = f"sdl-kline:{normalized_symbol}:{days}"
    cached = _get_local_cache(_SDL_CACHE, cache_key, _SDL_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    async with get_session(read_only=True) as session:
        res = await session.execute(
            text(
                "SELECT trade_date, open, high, low, close, volume, adj_factor FROM stock_daily_latest "
                "WHERE symbol = (CASE WHEN :s ~* '^(SH|SZ|BJ)[0-9]{6}$' THEN UPPER(:s) ELSE :s END) "
                "ORDER BY trade_date DESC LIMIT :l"
            ),
            {"s": normalized_symbol, "l": days},
        )
        items = []
        for r in res:
            adj_factor = r[6]
            items.append(
                {
                    "date": str(r[0]),
                    "open": _to_nominal_price(r[1], adj_factor),
                    "high": _to_nominal_price(r[2], adj_factor),
                    "low": _to_nominal_price(r[3], adj_factor),
                    "close": _to_nominal_price(r[4], adj_factor),
                    "volume": float(r[5]),
                }
            )
        items.reverse()
    payload = {"code": 200, "data": {"symbol": normalized_symbol, "items": items}}
    _set_local_cache(_SDL_CACHE, cache_key, payload, _SDL_CACHE_MAX_ENTRIES)
    return payload
