#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库清理脚本
清理旧的回测结果和 Pipeline 运行记录
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 PYTHONPATH
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.append(str(project_root))

from backend.services.engine.services.pipeline_persistence import PipelinePersistence
from backend.services.engine.services.strategy_loop_persistence import StrategyLoopPersistence

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cleanup_database")


async def run_cleanup(keep_days: int):
    logger.info(f"开始清理数据库，保留最近 {keep_days} 天的数据...")

    strategy_persistence = StrategyLoopPersistence()
    pipeline_persistence = PipelinePersistence()

    try:
        # 清理 strategy_loop_tasks
        logger.info("清理 strategy_loop_tasks...")
        tasks_deleted = await strategy_persistence.cleanup_old_tasks(keep_days=keep_days)
        logger.info(f"已清理 {tasks_deleted} 条策略回测任务记录")

        # 清理 pipeline_runs
        # 注意: PipelinePersistence.cleanup_old_runs 需要 user_id 和 tenant_id?
        # 让我们检查一下 PipelinePersistence.cleanup_old_runs 的定义
        # 之前看到的代码是:
        # async def cleanup_old_runs(self, *, user_id: str, tenant_id: str, keep_days: int = 30)
        # 这意味着它按用户清理。为了全局清理，我们可能需要一个新的方法或者修改它。

        # 这里为了简单起见，我们直接执行一个全局清理 SQL
        from sqlalchemy import text

        from backend.shared.database_manager_v2 import get_session

        async with get_session() as session:
            logger.info("执行全局 pipeline_runs 清理...")
            result = await session.execute(
                text("""
                    DELETE FROM pipeline_runs
                    WHERE created_at < (NOW() - make_interval(days => :keep_days))
                """),
                {"keep_days": int(keep_days)},
            )
            pipeline_deleted = result.rowcount
            logger.info(f"已清理 {pipeline_deleted} 条 Pipeline 运行记录")

        logger.info("数据库清理完成")

    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="清理 QuantMind 引擎数据库旧数据")
    parser.add_argument("--days", type=int, default=30, help="保留多少天的数据 (默认: 30)")

    args = parser.parse_args()

    asyncio.run(run_cleanup(args.days))


if __name__ == "__main__":
    main()
