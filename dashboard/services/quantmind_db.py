"""
QuantMind 数据库直连服务

直接连接 PostgreSQL 读取 stock_daily_latest 等表，
避免走 HTTP API 的额外开销。
"""

import os
import logging
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "quantmind"),
    "user": os.getenv("DB_USER", "quantmind"),
    "password": os.getenv("DB_PASSWORD", "quantmind2026"),
}


def _get_conn():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def check_connection() -> bool:
    """检查数据库连接"""
    try:
        conn = _get_conn()
        conn.close()
        return True
    except Exception:
        return False


def get_stock_daily(
    symbol: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = 120,
) -> pd.DataFrame:
    """获取股票日线数据"""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=days * 2)

    query = """
        SELECT trade_date, open, high, low, close, volume, adj_factor
        FROM stock_daily_latest
        WHERE symbol = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date ASC
    """
    try:
        conn = _get_conn()
        df = pd.read_sql(query, conn, params=(symbol, start_date, end_date))
        conn.close()

        if df.empty:
            return df

        # 应用复权因子
        if "adj_factor" in df.columns:
            latest_adj = df["adj_factor"].iloc[-1]
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col] * df["adj_factor"] / latest_adj

        return df
    except Exception as e:
        logger.error("Failed to get stock daily: %s", e)
        return pd.DataFrame()


def get_latest_indices() -> dict[str, dict[str, Any]]:
    """获取主要指数最新数据"""
    indices = {
        "沪深300": "SH000300",
        "中证500": "SH000905",
        "中证1000": "SH000852",
        "中证800": "SH000906",
    }

    result = {}
    try:
        conn = _get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        for name, symbol in indices.items():
            cursor.execute(
                """
                SELECT close, open, high, low, volume,
                       CASE WHEN open > 0 THEN (close - open) / open * 100 ELSE 0 END as change_pct
                FROM stock_daily_latest
                WHERE symbol = %s
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (symbol,),
            )
            row = cursor.fetchone()
            if row:
                result[name] = dict(row)

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error("Failed to get indices: %s", e)

    return result


def get_market_breadth() -> dict[str, int]:
    """获取市场涨跌分布"""
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # 获取最新交易日
        cursor.execute(
            "SELECT DISTINCT trade_date FROM stock_daily_latest ORDER BY trade_date DESC LIMIT 1"
        )
        latest_date = cursor.fetchone()[0]

        # 计算涨跌幅分布
        cursor.execute(
            """
            WITH changes AS (
                SELECT
                    symbol,
                    CASE
                        WHEN LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) > 0
                        THEN (close - LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date))
                             / LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) * 100
                        ELSE 0
                    END as change_pct
                FROM stock_daily_latest
                WHERE trade_date >= %s - INTERVAL '5 days'
            )
            SELECT
                SUM(CASE WHEN change_pct >= 9.9 THEN 1 ELSE 0 END) as limit_up,
                SUM(CASE WHEN change_pct >= 5 AND change_pct < 9.9 THEN 1 ELSE 0 END) as up_gt5,
                SUM(CASE WHEN change_pct >= 0 AND change_pct < 5 THEN 1 ELSE 0 END) as up_0_5,
                SUM(CASE WHEN change_pct = 0 THEN 1 ELSE 0 END) as flat,
                SUM(CASE WHEN change_pct < 0 AND change_pct > -5 THEN 1 ELSE 0 END) as down_0_5,
                SUM(CASE WHEN change_pct <= -5 AND change_pct > -9.9 THEN 1 ELSE 0 END) as down_gt5,
                SUM(CASE WHEN change_pct <= -9.9 THEN 1 ELSE 0 END) as limit_down
            FROM changes
            WHERE change_pct IS NOT NULL
            """,
            (latest_date,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return {
                "limit_up": row[0] or 0,
                "up_gt5": row[1] or 0,
                "up_0_5": row[2] or 0,
                "flat": row[3] or 0,
                "down_0_5": row[4] or 0,
                "down_gt5": row[5] or 0,
                "limit_down": row[6] or 0,
            }
    except Exception as e:
        logger.error("Failed to get market breadth: %s", e)

    return {
        "limit_up": 0, "up_gt5": 0, "up_0_5": 0,
        "flat": 0, "down_0_5": 0, "down_gt5": 0, "limit_down": 0,
    }


def get_hot_sectors(limit: int = 10) -> list[dict[str, Any]]:
    """获取热门板块（按行业分组统计涨跌幅）"""
    try:
        conn = _get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            WITH latest AS (
                SELECT DISTINCT trade_date FROM stock_daily_latest
                ORDER BY trade_date DESC LIMIT 1
            ),
            prev AS (
                SELECT DISTINCT trade_date FROM stock_daily_latest
                ORDER BY trade_date DESC LIMIT 1 OFFSET 1
            ),
            today_data AS (
                SELECT s.symbol, s.close,
                       m.sector
                FROM stock_daily_latest s
                JOIN latest l ON s.trade_date = l.trade_date
                LEFT JOIN stocks m ON (
                    m.symbol = SUBSTRING(s.symbol, 3) || '.' || LEFT(s.symbol, 2)
                )
                WHERE m.sector IS NOT NULL
            ),
            prev_data AS (
                SELECT s.symbol, s.close
                FROM stock_daily_latest s
                JOIN prev p ON s.trade_date = p.trade_date
            )
            SELECT
                t.sector as name,
                AVG((t.close - p.close) / p.close * 100) as change_pct,
                COUNT(*) as stock_count
            FROM today_data t
            JOIN prev_data p ON t.symbol = p.symbol
            WHERE p.close > 0
            GROUP BY t.sector
            ORDER BY change_pct DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error("Failed to get hot sectors: %s", e)
        return []


def get_user_portfolio(user_id: str) -> list[dict[str, Any]]:
    """获取用户持仓"""
    try:
        conn = _get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT symbol, quantity, avg_cost, current_price,
                   market_value, profit_loss, profit_pct
            FROM portfolio_positions
            WHERE user_id = %s AND quantity > 0
            ORDER BY market_value DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error("Failed to get portfolio: %s", e)
        return []


def get_stock_list(market: str = "A", limit: int = 100) -> list[dict[str, str]]:
    """获取股票列表"""
    try:
        conn = _get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT symbol, name, sector, industry
            FROM stock_master
            WHERE market = %s AND is_active = true
            ORDER BY symbol
            LIMIT %s
            """,
            (market, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error("Failed to get stock list: %s", e)
        return []


def get_rd_agent_factors(limit: int = 20) -> list[dict[str, Any]]:
    """获取 RD-Agent 因子列表"""
    try:
        conn = _get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT factor_name, description, ic, ir, sharpe,
                   created_at, status
            FROM rd_agent_factors
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error("Failed to get RD-Agent factors: %s", e)
        return []
