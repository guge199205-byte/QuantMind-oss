#!/usr/bin/env python3
"""
基础设施健康检查脚本
检查PostgreSQL主从、Redis哨兵集群状态
"""

from shared.redis_sentinel_client import RedisSentinelClient
from shared.database_manager_v2 import DatabaseManager
import asyncio
import sys
from datetime import datetime

# 添加backend路径
sys.path.insert(0, "/app")


async def check_database():
    """检查数据库健康状态"""
    print("\n" + "=" * 60)
    print("PostgreSQL Health Check")
    print("=" * 60)

    try:
        db_manager = DatabaseManager()
        await db_manager.initialize()

        # 健康检查
        health = await db_manager.health_check()

        # 打印主库状态
        print("\n📊 Master Database:")
        if health["master"]:
            print("  ✅ Status: HEALTHY")
        else:
            print("  ❌ Status: UNHEALTHY")

        # 打印从库状态
        print(f"\n📊 Slave Databases ({len(health['slaves'])}):")
        for slave in health["slaves"]:
            status = "✅ HEALTHY" if slave["healthy"] else "❌ UNHEALTHY"
            print(f"  Slave {slave['index']}: {status}")

        # 连接池状态
        pool_status = await db_manager.get_pool_status()

        print("\n📊 Connection Pool Status:")
        if "master" in pool_status:
            master_pool = pool_status["master"]
            print("  Master:")
            print(f"    Size: {master_pool['size']}")
            print(f"    Checked In: {master_pool['checked_in']}")
            print(f"    Checked Out: {master_pool['checked_out']}")
            print(f"    Overflow: {master_pool['overflow']}")
            print(f"    Total: {master_pool['total']}")

        for slave in pool_status.get("slaves", []):
            print(f"  Slave {slave['index']}:")
            print(f"    Size: {slave['size']}")
            print(f"    Checked In: {slave['checked_in']}")
            print(f"    Checked Out: {slave['checked_out']}")
            print(f"    Overflow: {slave['overflow']}")
            print(f"    Total: {slave['total']}")

        await db_manager.close()

        # 返回整体健康状态
        all_healthy = health["master"] and all(
            s["healthy"] for s in health["slaves"])
        return all_healthy

    except Exception as e:
        print(f"\n❌ Database health check failed: {e}")
        return False


def check_redis():
    """检查Redis健康状态"""
    print("\n" + "=" * 60)
    print("Redis Sentinel Health Check")
    print("=" * 60)

    try:
        redis_client = RedisSentinelClient()

        # 健康检查
        health = redis_client.health_check()

        # 打印状态
        print("\n📊 Redis Status:")
        print(
            f"  Master: {'✅ HEALTHY' if health['master'] else '❌ UNHEALTHY'}")
        print(f"  Slave: {'✅ HEALTHY' if health['slave'] else '❌ UNHEALTHY'}")
        print(
            f"  Sentinel: {'✅ HEALTHY' if health['sentinel'] else '❌ UNHEALTHY'}")

        # 主库信息
        try:
            master_info = redis_client.get_master_info()
            print("\n📊 Master Info:")
            print(f"  Host: {master_info[0]}")
            print(f"  Port: {master_info[1]}")
        except Exception as e:
            print(f"\n⚠️  Cannot get master info: {e}")

        # 从库信息
        try:
            slave_info = redis_client.get_slave_info()
            print(f"\n📊 Slave Info ({len(slave_info)}):")
            for idx, slave in enumerate(slave_info, 1):
                print(f"  Slave {idx}:")
                print(f"    Host: {slave[0]}")
                print(f"    Port: {slave[1]}")
        except Exception as e:
            print(f"\n⚠️  Cannot get slave info: {e}")

        redis_client.close()

        # 返回整体健康状态
        return health["master"] and health["sentinel"]

    except Exception as e:
        print(f"\n❌ Redis health check failed: {e}")
        return False


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("QuantMind Infrastructure Health Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查数据库
    db_healthy = await check_database()

    # 检查Redis
    redis_healthy = check_redis()

    # 汇总
    print("\n" + "=" * 60)
    print("Health Check Summary")
    print("=" * 60)
    print(f"  PostgreSQL: {'✅ HEALTHY' if db_healthy else '❌ UNHEALTHY'}")
    print(f"  Redis: {'✅ HEALTHY' if redis_healthy else '❌ UNHEALTHY'}")

    # 退出码
    if db_healthy and redis_healthy:
        print("\n✅ All systems operational")
        sys.exit(0)
    else:
        print("\n❌ Some systems are unhealthy")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
