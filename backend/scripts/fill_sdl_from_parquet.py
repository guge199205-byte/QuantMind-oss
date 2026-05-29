import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import asyncio
import time
import asyncpg

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 加载凭据
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "quantmind")
DB_USER = os.getenv("DB_USER", "quantmind")
DB_PASS = os.getenv("DB_PASSWORD", "quantmind2026")

async def fill_data_super_fast(file_path):
    print(f"Connecting to DB via asyncpg: {DB_HOST}:{DB_PORT}")
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME
    )
    
    try:
        print(f"Reading {file_path}...")
        df = pd.read_parquet(file_path)
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date # 转为 date 类型以适配 PG
        df_2026 = df[df['trade_date'] >= pd.to_datetime('2026-01-01').date()].copy()
        
        # 预处理数据
        df_2026['amount'] = df_2026['close'] * df_2026['volume']
        df_2026['symbol'] = df_2026['symbol'].str.upper()
        df_2026['adj_factor'] = df_2026['factor'].astype(float)
        df_2026['stock_name'] = ""
        df_2026['industry'] = ""
        
        # 严格匹配数据库列顺序
        cols = ['trade_date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'amount', 'adj_factor', 'stock_name', 'industry']
        data_to_load = df_2026[cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # 转换为元组列表
        records = list(data_to_load.itertuples(index=False, name=None))
        
        print(f"Ready to import {len(records):,} records...")
        
        start_time = time.time()
        # 使用 COPY 指令，这是 PG 最快的方式
        await conn.copy_records_to_table(
            'stock_daily_latest', 
            records=records, 
            columns=cols
        )
        print(f"Successfully imported everything in {time.time() - start_time:.2f}s!")

    finally:
        await conn.close()

if __name__ == "__main__":
    target_file = '/Users/qusong/git/quantmind/data/ohlcv_complete_2016_2026.parquet'
    asyncio.run(fill_data_super_fast(target_file))
