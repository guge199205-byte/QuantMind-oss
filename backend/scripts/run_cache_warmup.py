import os
import sys

# 关键：在 import 任何项目模块之前，强制清理 Redis 密码
if 'REDIS_PASSWORD' in os.environ:
    del os.environ['REDIS_PASSWORD']

import asyncio
from pathlib import Path

# 添加项目根目录
PROJECT_ROOT = Path("/Users/qusong/git/quant")
sys.path.insert(0, str(PROJECT_ROOT))

# 环境变量强制设置
os.environ['DB_HOST'] = '127.0.0.1'
os.environ['DB_USER'] = 'quantmind'
os.environ['DB_PASSWORD'] = 'quantmind2026'
os.environ['REDIS_HOST'] = '127.0.0.1'
os.environ['REDIS_PORT'] = '6379'

# 再次确保 (防止某些模块内部调用 load_dotenv)
os.environ['REDIS_PASSWORD'] = '' # 有些库可能处理 None 和空字符串不同，如果还是不行我再试别的

from backend.shared.market_data.stock_daily_latest_cache import stock_latest_cache

async def warmup():
    print('Starting Redis cache warmup...')
    # 强制覆盖配置对象的密码为 None
    stock_latest_cache.redis.config.password = None
    
    try:
        # 1. 初始化连接
        stock_latest_cache.redis._ensure_connection()
        master = stock_latest_cache.redis._master_client
        
        # 2. 清理旧缓存
        keys = master.keys('qm:stock_latest:*')
        if keys:
            key_list = [k.decode() if isinstance(k, bytes) else k for k in keys]
            stock_latest_cache.redis.delete(*key_list)
            print(f'Cleared {len(key_list)} market data keys.')
            
        kline_keys = master.keys('qm:research:kline:*')
        if kline_keys:
            kline_list = [k.decode() if isinstance(k, bytes) else k for k in kline_keys]
            stock_latest_cache.redis.delete(*kline_list)
            print(f'Cleared {len(kline_list)} kline cache keys.')
            
    except Exception as e:
        print(f'Clear cache warning: {e}')

    # 3. 预热最新行情
    count = await stock_latest_cache.warmup_cache()
    print(f'Cache warmup complete! Cached {count} symbols.')

if __name__ == '__main__':
    asyncio.run(warmup())
