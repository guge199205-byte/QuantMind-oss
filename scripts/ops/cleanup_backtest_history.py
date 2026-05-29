#!/usr/bin/env python3
"""
QuantMind 回测历史清理工具
--------------------------
功能：清理 qlib_backtest_runs 表中的历史记录。
支持：
1. 按日期清理（保留最近 X 天）
2. 按数量清理（保留最近 X 条）
3. 全部清理
"""

import os
import sys
import argparse
import logging
import psycopg2
import redis
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 设置项目根目录
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CleanupHistory")

def get_db_connection():
    """获取数据库连接"""
    host = os.getenv("DB_MASTER_HOST", "127.0.0.1")
    port = os.getenv("DB_MASTER_PORT", "5432")
    user = os.getenv("DB_USER", "quantmind")
    password = os.getenv("DB_PASSWORD", "admin123")
    dbname = os.getenv("DB_NAME", "quantmind")
    
    conn_str = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    return psycopg2.connect(conn_str)

def clear_redis_cache():
    """清空 Redis 中的回测缓存"""
    try:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD", None)
        db = int(os.getenv("REDIS_DB_CACHE", "5"))
        
        r = redis.Redis(host=host, port=port, password=password, db=db)
        keys = r.keys("qlib:*")
        if keys:
            r.delete(*keys)
            logger.info(f"⚡ 已清理 Redis 缓存，共删除 {len(keys)} 个 Key。")
        else:
            logger.info("ℹ️ Redis 缓存中无匹配的 qlib:* 记录。")
    except Exception as e:
        logger.warning(f"⚠️ 清理 Redis 缓存失败: {e}")

def cleanup_all(conn):
    """清理所有回测记录"""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM qlib_backtest_runs;")
        count = cur.rowcount
        conn.commit()
        logger.info(f"✅ 已清理所有回测记录，共删除 {count} 条。")

def cleanup_by_days(conn, days):
    """清理 X 天之前的记录"""
    cutoff_date = datetime.now() - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM qlib_backtest_runs WHERE created_at < %s;",
            (cutoff_date,)
        )
        count = cur.rowcount
        conn.commit()
        logger.info(f"✅ 已清理 {days} 天之前的记录（{cutoff_date.date()}之前），共删除 {count} 条。")

def cleanup_keep_n(conn, keep_n):
    """每个用户仅保留最近 N 条，其余删除"""
    with conn.cursor() as cur:
        # 使用窗口函数标记序号并删除序号大于 N 的记录
        cur.execute("""
            DELETE FROM qlib_backtest_runs
            WHERE backtest_id IN (
                SELECT backtest_id FROM (
                    SELECT backtest_id, 
                           ROW_NUMBER() OVER (PARTITION BY user_id, tenant_id ORDER BY created_at DESC) as rn
                    FROM qlib_backtest_runs
                ) t
                WHERE t.rn > %s
            );
        """, (keep_n,))
        count = cur.rowcount
        conn.commit()
        logger.info(f"✅ 冗余清理完成：每位用户保留最近 {keep_n} 条记录，共删除 {count} 条。")

def main():
    parser = argparse.ArgumentParser(description="QuantMind Backtest History Cleanup")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="清理所有回测历史")
    group.add_argument("--days", type=int, help="保留最近 X 天的历史")
    group.add_argument("--keep", type=int, help="每个用户保留最近 X 条历史")
    
    args = parser.parse_args()
    
    try:
        conn = get_db_connection()
        if args.all:
            confirm = input("⚠️  确定要永久删除所有回测历史吗？(y/N): ")
            if confirm.lower() == 'y':
                cleanup_all(conn)
                clear_redis_cache()
            else:
                logger.info("操作已取消。")
        elif args.days is not None:
            cleanup_by_days(conn, args.days)
            clear_redis_cache()
        elif args.keep is not None:
            cleanup_keep_n(conn, args.keep)
            clear_redis_cache()
            
    except Exception as e:
        logger.error(f"❌ 清理失败: {e}")
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
    return 0

if __name__ == "__main__":
    exit(main())
