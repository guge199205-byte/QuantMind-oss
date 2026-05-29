#!/usr/bin/env python3
"""回填 stock_daily_latest 中被 NULL 的基本面列。

Qlib 导入只写了 OHLCV，导致 industry/is_st/pe_ttm/pb/roe/ln_mv_total 等列丢失。
本脚本从历史数据回填这些列（行业、ST 标记不变，估值指标用最近有效值）。

用法:
    python backfill_sdl_features.py                  # 回填所有缺失日期
    python backfill_sdl_features.py --since 2026-05-09
"""

import argparse
import asyncio
import os
import sys
from datetime import date, datetime
from pathlib import Path

# 容器内 vs 主机
if os.path.exists("/app"):
    DB_URL = "postgresql://quantmind:quantmind2026@db:5432/quantmind"
else:
    DB_URL = "postgresql://quantmind:quantmind2026@localhost:5432/quantmind"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# 需要回填的列及其回填策略
# "copy" = 直接从最近有效值复制（行业、ST等不变的属性）
# "forward_fill" = 前向填充（估值指标用最近值）
def normalize_symbol(sym: str) -> str:
    """统一符号格式为 600519.SH（标准格式）。"""
    s = sym.strip().upper()
    if len(s) > 2 and s[:2] in ("SH", "SZ", "BJ") and s[2:].isdigit():
        return f"{s[2:]}.{s[:2]}"
    return s


BACKFILL_COLUMNS = {
    # 基本面（不变属性，用最近有效值）
    "industry": "copy",
    "is_st": "copy",
    "stock_name": "copy",
    "listing_market": "copy",
    "province": "copy",
    # 估值指标（前向填充）
    "pe_ttm": "forward_fill",
    "pb": "forward_fill",
    "roe": "forward_fill",
    "ln_mv_total": "forward_fill",
    "float_mv": "forward_fill",
    "total_mv": "forward_fill",
    "bp": "forward_fill",
    "ep_ttm": "forward_fill",
    # 行业分类
    "ind_code_l1": "copy",
    "ind_code_l2": "copy",
}


async def backfill(since: date):
    import asyncpg

    conn = await asyncpg.connect(DB_URL)
    try:
        # 1. 找到 since 之前最近一个有完整数据的日期
        ref_row = await conn.fetchrow("""
            SELECT trade_date FROM stock_daily_latest
            WHERE trade_date < $1 AND industry IS NOT NULL
            ORDER BY trade_date DESC LIMIT 1
        """, since)

        if not ref_row:
            _log("ERROR: 找不到有完整数据的参考日期")
            return

        ref_date = ref_row["trade_date"]
        _log(f"参考日期: {ref_date}")

        # 2. 获取参考日期的数据（作为回填源）
        ref_data = await conn.fetch("""
            SELECT symbol, industry, is_st, stock_name, listing_market, province,
                   pe_ttm, pb, roe, ln_mv_total, float_mv, total_mv, bp, ep_ttm,
                   ind_code_l1, ind_code_l2
            FROM stock_daily_latest WHERE trade_date = $1
        """, ref_date)

        ref_map = {}
        for r in ref_data:
            ref_map[normalize_symbol(r["symbol"])] = dict(r)

        _log(f"参考数据: {len(ref_map)} 只股票")

        # 3. 找到需要回填的日期（industry IS NULL 的日期）
        dates = await conn.fetch("""
            SELECT DISTINCT trade_date FROM stock_daily_latest
            WHERE trade_date >= $1 AND industry IS NULL
            ORDER BY trade_date
        """, since)

        if not dates:
            _log("无需回填（所有日期都有数据）")
            return

        _log(f"需要回填: {len(dates)} 天, {dates[0]['trade_date']} ~ {dates[-1]['trade_date']}")

        # 4. 逐日回填
        total_updated = 0
        for d_row in dates:
            d = d_row["trade_date"]

            # 获取该日所有股票
            day_stocks = await conn.fetch("""
                SELECT symbol FROM stock_daily_latest WHERE trade_date = $1
            """, d)

            updated = 0
            for s_row in day_stocks:
                sym = s_row["symbol"]
                ref = ref_map.get(normalize_symbol(sym))
                if not ref:
                    continue

                # 构建 UPDATE SET 子句
                set_parts = []
                params = [d, sym]
                idx = 3
                for col in BACKFILL_COLUMNS:
                    val = ref.get(col)
                    if val is not None:
                        set_parts.append(f"{col} = ${idx}")
                        params.append(val)
                        idx += 1

                if not set_parts:
                    continue

                sql = f"""
                    UPDATE stock_daily_latest
                    SET {', '.join(set_parts)}
                    WHERE trade_date = $1 AND symbol = $2
                """
                await conn.execute(sql, *params)
                updated += 1

            total_updated += updated
            _log(f"  {d}: 回填 {updated} 只股票")

        _log(f"完成: 共回填 {total_updated} 条记录")

        # 5. 对于 pe_ttm/pb 等估值指标，用前向填充（取最近有效值）
        _log("前向填充估值指标...")
        for d_row in dates:
            d = d_row["trade_date"]
            # 使用 symbol 标准化后的 JOIN
            await conn.execute("""
                UPDATE stock_daily_latest AS t
                SET pe_ttm = sub.pe_ttm, pb = sub.pb, roe = sub.roe,
                    ln_mv_total = sub.ln_mv_total, bp = sub.bp, ep_ttm = sub.ep_ttm
                FROM (
                    SELECT DISTINCT ON (s1.symbol)
                        s1.symbol, s2.pe_ttm, s2.pb, s2.roe, s2.ln_mv_total, s2.bp, s2.ep_ttm
                    FROM stock_daily_latest s1
                    JOIN stock_daily_latest s2 ON (
                        CASE WHEN s2.symbol ~ '^[0-9]' THEN s2.symbol
                             ELSE substring(s2.symbol from 3) || '.' || substring(s2.symbol from 1 for 2)
                        END
                        =
                        CASE WHEN s1.symbol ~ '^[0-9]' THEN s1.symbol
                             ELSE substring(s1.symbol from 3) || '.' || substring(s1.symbol from 1 for 2)
                        END
                    )
                    WHERE s1.trade_date = $1
                        AND s2.trade_date < $1
                        AND s2.pe_ttm IS NOT NULL
                    ORDER BY s1.symbol, s2.trade_date DESC
                ) sub
                WHERE t.trade_date = $1 AND t.symbol = sub.symbol AND t.pe_ttm IS NULL
            """, d)

        _log("估值指标前向填充完成")

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="回填 stock_daily_latest 基本面列")
    parser.add_argument("--since", default="2026-05-09", help="回填起始日期")
    args = parser.parse_args()

    since = date.fromisoformat(args.since)
    _log(f"回填起始日期: {since}")
    asyncio.run(backfill(since))


if __name__ == "__main__":
    main()
