"""
港股/美股基本面数据同步
========================
从 yfinance 获取 PE/PB/ROE/EPS/股息率/市值等基本面数据，
更新到 stock_daily_latest_hk / stock_daily_latest_us 表。

用法:
    python sync_market_fundamentals.py [--market HK|US|ALL] [--dry-run]
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _get_engine():
    db_url = (
        f"postgresql://{os.getenv('DB_USER', 'quantmind')}:{os.getenv('DB_PASSWORD', 'quantmind')}"
        f"@{os.getenv('DB_HOST', 'quantmind-db')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'quantmind')}"
    )
    return create_engine(db_url)


# ── yfinance 批量获取 ──────────────────────────────────────────────

def _fetch_yfinance_batch(symbols: list[str], market: str) -> dict[str, dict]:
    """批量获取 yfinance 基本面数据。"""
    import yfinance as yf

    results = {}
    batch_size = 50  # yfinance 支持批量下载

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        # 构建 yfinance ticker 格式
        if market == "HK":
            tickers = [f"{s.zfill(4)}.HK" for s in batch]
        elif market == "US":
            tickers = batch
        else:
            continue

        ticker_str = " ".join(tickers)
        log.info(f"  Fetching {market} batch {i // batch_size + 1}: {len(batch)} symbols")

        try:
            data = yf.Tickers(ticker_str)
            for ticker_sym in tickers:
                try:
                    info = data.tickers[ticker_sym.replace('.', '-')].info
                    if not info or info.get('trailingPE') is None:
                        continue

                    # 提取原始 symbol
                    if market == "HK":
                        raw_sym = ticker_sym.replace('.HK', '')
                    else:
                        raw_sym = ticker_sym

                    # yfinance ROE 是小数 (0.21 = 21%)，转为百分比
                    roe_raw = info.get('returnOnEquity')
                    roe_pct = roe_raw * 100 if roe_raw is not None else None

                    results[raw_sym] = {
                        'pe_ttm': info.get('trailingPE'),
                        'forward_pe': info.get('forwardPE'),
                        'pb': info.get('priceToBook'),
                        'roe': roe_pct,
                        'eps_ttm': info.get('epsTrailingTwelveMonths'),
                        'eps_forward': info.get('epsForward'),
                        'bv': info.get('bookValue'),
                        'market_cap': info.get('marketCap'),
                        'total_revenue': info.get('totalRevenue'),
                        'net_income': info.get('netIncomeToCommon'),
                        'profit_margin': info.get('profitMargins'),
                        'revenue_growth': info.get('revenueGrowth'),
                        'earnings_growth': info.get('earningsGrowth'),
                        'beta': info.get('beta'),
                        'industry': info.get('industry', ''),
                        'sector': info.get('sector', ''),
                        'name': info.get('longName', info.get('shortName', '')),
                    }
                except Exception:
                    continue
        except Exception as e:
            log.warning(f"  yfinance batch error: {e}")

        # 避免请求过快
        if i + batch_size < len(symbols):
            time.sleep(1)

    return results


def _fetch_akshare_hk(symbols: list[str]) -> dict[str, dict]:
    """获取 akshare 港股财务指标。"""
    import akshare as ak

    results = {}
    for i, sym in enumerate(symbols):
        try:
            df = ak.stock_hk_financial_indicator_em(symbol=sym.zfill(5))
            if df is None or df.empty:
                continue

            row = df.iloc[0]
            results[sym] = {
                'pe_ttm': float(row.get('市盈率', 0) or 0),
                'pb': float(row.get('市净率', 0) or 0),
                'roe': float(row.get('股东权益回报率(%)', 0) or 0),
                'eps_ttm': float(row.get('基本每股收益(元)', 0) or 0),
                'bv': float(row.get('每股净资产(元)', 0) or 0),
                'dividend_yield': float(row.get('股息率TTM(%)', 0) or 0),
                'market_cap': float(row.get('总市值(港元)', 0) or 0),
                'total_revenue': float(row.get('营业总收入', 0) or 0),
                'net_income': float(row.get('净利润', 0) or 0),
                'profit_margin': float(row.get('销售净利率(%)', 0) or 0),
                'revenue_growth': float(row.get('营业总收入滚动环比增长(%)', 0) or 0),
                'earnings_growth': float(row.get('净利润滚动环比增长(%)', 0) or 0),
            }
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            log.info(f"  akshare HK progress: {i + 1}/{len(symbols)}")
            time.sleep(2)

    return results


# ── 数据库更新 ──────────────────────────────────────────────────────

def _update_db(engine, table: str, data: dict[str, dict], market: str) -> int:
    """更新数据库中的基本面数据。"""
    if not data:
        return 0

    updated = 0
    with engine.begin() as conn:
        for sym, fields in data.items():
            # 构建 SET 子句
            set_parts = []
            params = {'sym': sym}

            field_map = {
                'pe_ttm': 'pe_ttm',
                'pb': 'pb',
                'roe': 'roe',
                'eps_ttm': 'ep_ttm',
                'bv': 'bp',
                'market_cap': 'total_mv',
                'industry': 'industry',
                'name': 'name',
            }

            for src_key, db_col in field_map.items():
                val = fields.get(src_key)
                if val is not None and val != 0:
                    if isinstance(val, str):
                        set_parts.append(f"{db_col} = :{src_key}")
                    else:
                        set_parts.append(f"{db_col} = :{src_key}")
                    params[src_key] = val

            if not set_parts:
                continue

            sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE symbol = :sym"
            res = conn.execute(text(sql), params)
            updated += res.rowcount

    return updated


# ── 主流程 ──────────────────────────────────────────────────────────

def sync_market_fundamentals(market: str, dry_run: bool = False) -> dict:
    """同步指定市场的基本面数据。"""
    engine = _get_engine()
    market = market.upper()

    table_map = {
        "HK": "stock_daily_latest_hk",
        "US": "stock_daily_latest_us",
    }

    if market not in table_map:
        return {"error": f"unsupported market: {market}"}

    table = table_map[market]

    # 获取 symbol 列表
    with engine.begin() as conn:
        rows = conn.execute(text(f"SELECT symbol FROM {table}")).fetchall()
        symbols = [r[0] for r in rows]

    log.info(f"Syncing {market} fundamentals: {len(symbols)} symbols")

    if dry_run:
        log.info("DRY RUN - not updating database")
        return {"market": market, "symbols": len(symbols), "dry_run": True}

    # 获取数据
    if market == "HK":
        # 港股用 akshare（yfinance 在容器内连不上）
        log.info("Fetching HK from akshare...")
        data = _fetch_akshare_hk(symbols)
        log.info(f"  akshare: {len(data)} symbols with data")
    else:
        # US 用 yfinance
        data = _fetch_yfinance_batch(symbols, market)

    log.info(f"Total symbols with data: {len(data)}")

    # 更新数据库
    updated = _update_db(engine, table, data, market)
    log.info(f"Updated {updated} rows in {table}")

    return {
        "market": market,
        "symbols_total": len(symbols),
        "symbols_with_data": len(data),
        "rows_updated": updated,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync market fundamentals")
    parser.add_argument("--market", default="ALL", choices=["HK", "US", "ALL"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.market == "ALL":
        for m in ["HK", "US"]:
            result = sync_market_fundamentals(m, args.dry_run)
            log.info(f"{m} result: {result}")
    else:
        result = sync_market_fundamentals(args.market, args.dry_run)
        log.info(f"Result: {result}")


if __name__ == "__main__":
    main()
