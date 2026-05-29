"""
多级缓存使用示例
"""

import asyncio

from multi_level_cache import MultiLevelCache


# 示例 1: 基本使用
async def example_basic():
    # 初始化缓存 (不使用 Redis)
    cache = MultiLevelCache()

    # 设置缓存
    await cache.set("user:123", {"name": "Alice", "age": 30})

    # 获取缓存
    user = await cache.get("user:123")
    print(f"User: {user}")

    # 获取统计
    stats = cache.get_stats()
    print(f"Stats: {stats}")


# 示例 2: 使用装饰器
async def example_decorator():
    cache = MultiLevelCache()

    @cache.cached(prefix="user", ttl_l1=60, ttl_l2=300)
    async def get_user(user_id: int):
        # 模拟数据库查询
        await asyncio.sleep(0.1)
        return {"id": user_id, "name": f"User{user_id}"}

    # 第一次调用 - 从数据库加载
    user1 = await get_user(123)
    print(f"First call: {user1}")

    # 第二次调用 - 从缓存获取
    user2 = await get_user(123)
    print(f"Second call (cached): {user2}")

    print(f"Stats: {cache.get_stats()}")


# 示例 3: 使用 loader 函数
async def example_loader():
    cache = MultiLevelCache()

    async def fetch_stock_data(symbol: str):
        # 模拟API调用
        await asyncio.sleep(0.2)
        return {"symbol": symbol, "price": 100.50}

    # 使用 loader
    stock = await cache.get("stock:AAPL", loader=lambda: fetch_stock_data("AAPL"), ttl_l1=30, ttl_l2=120)
    print(f"Stock: {stock}")


if __name__ == "__main__":
    print("=== Example 1: Basic Usage ===")
    asyncio.run(example_basic())

    print("\n=== Example 2: Decorator ===")
    asyncio.run(example_decorator())

    print("\n=== Example 3: Loader ===")
    asyncio.run(example_loader())
