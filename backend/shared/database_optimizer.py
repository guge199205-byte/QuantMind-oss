"""
数据库性能优化工具

功能:
1. 连接池配置优化
2. 自动添加索引
3. N+1 查询检测
4. 慢查询分析
5. 批量操作优化
"""

import logging
import time
from typing import Any, Dict, List

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """数据库优化器"""

    def __init__(self, engine: Engine, slow_query_threshold: float = 1.0):
        self.engine = engine
        self.slow_query_threshold = slow_query_threshold
        self.query_stats = []
        self._setup_monitoring()

    def _setup_monitoring(self):
        """设置查询监控"""

        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault("query_start_time", []).append(time.time())

        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total_time = time.time() - conn.info["query_start_time"].pop()

            # 记录慢查询
            if total_time > self.slow_query_threshold:
                logger.warning(f"Slow query ({total_time:.2f}s): {statement[:200]}")
                self.query_stats.append(
                    {
                        "statement": statement,
                        "time": total_time,
                        "parameters": parameters,
                    }
                )

    def get_recommended_indexes(self, model_class) -> list[dict[str, Any]]:
        """分析并推荐索引"""
        inspector = inspect(self.engine)
        table_name = model_class.__tablename__
        existing_indexes = inspector.get_indexes(table_name)

        recommendations = []

        # 检查外键是否有索引
        foreign_keys = inspector.get_foreign_keys(table_name)
        for fk in foreign_keys:
            column = fk["constrained_columns"][0]
            has_index = any(column in idx["column_names"] for idx in existing_indexes)
            if not has_index:
                recommendations.append(
                    {
                        "table": table_name,
                        "column": column,
                        "reason": "Foreign key without index",
                        "sql": f"CREATE INDEX idx_{table_name}_{column} ON {table_name}({column});",
                    }
                )

        return recommendations

    def apply_recommended_indexes(self, recommendations: list[dict[str, Any]]):
        """应用推荐的索引"""
        with self.engine.connect() as conn:
            for rec in recommendations:
                try:
                    logger.info(f"Creating index: {rec['sql']}")
                    conn.execute(text(rec["sql"]))
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed to create index: {e}")

    def optimize_connection_pool(self, **kwargs):
        """优化连接池配置"""
        recommended = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        }

        current = {
            "pool_size": self.engine.pool.size(),
            "max_overflow": self.engine.pool._max_overflow,
        }

        logger.info(f"Current pool config: {current}")
        logger.info(f"Recommended config: {recommended}")

        return recommended

    def detect_n_plus_one(self, session: Session, query):
        """检测 N+1 查询问题"""
        query_count_before = len(self.query_stats)

        # 执行查询
        session.execute(query).scalars().all()

        query_count_after = len(self.query_stats)
        queries_executed = query_count_after - query_count_before

        # 如果查询数量 > 1，可能存在 N+1 问题
        if queries_executed > 1:
            logger.warning(f"Potential N+1 query: {queries_executed} queries executed")
            return True

        return False

    def get_slow_queries(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取慢查询"""
        sorted_queries = sorted(self.query_stats, key=lambda x: x["time"], reverse=True)
        return sorted_queries[:limit]

    def analyze_query_plan(self, sql: str):
        """分析查询计划"""
        with self.engine.connect() as conn:
            result = conn.execute(text(f"EXPLAIN {sql}"))
            plan = [dict(row) for row in result]
            return plan


class BatchOperationHelper:
    """批量操作助手"""

    @staticmethod
    def bulk_insert(
        session: Session,
        model_class,
        data: list[dict[str, Any]],
        batch_size: int = 1000,
    ):
        """批量插入"""
        total = len(data)
        for i in range(0, total, batch_size):
            batch = data[i : i + batch_size]
            objects = [model_class(**item) for item in batch]
            session.bulk_save_objects(objects)
            session.commit()
            logger.info(f"Inserted {i + len(batch)}/{total} records")

    @staticmethod
    def bulk_update(
        session: Session,
        model_class,
        updates: list[dict[str, Any]],
        batch_size: int = 1000,
    ):
        """批量更新"""
        total = len(updates)
        for i in range(0, total, batch_size):
            batch = updates[i : i + batch_size]
            session.bulk_update_mappings(model_class, batch)
            session.commit()
            logger.info(f"Updated {i + len(batch)}/{total} records")


# 使用示例
"""
# 1. 初始化优化器
optimizer = DatabaseOptimizer(engine, slow_query_threshold=0.5)

# 2. 获取索引推荐
recommendations = optimizer.get_recommended_indexes(UserModel)
optimizer.apply_recommended_indexes(recommendations)

# 3. 检测 N+1 查询
from sqlalchemy.orm import joinedload
query = select(User).options(joinedload(User.profile))
is_n_plus_one = optimizer.detect_n_plus_one(session, query)

# 4. 批量操作
BatchOperationHelper.bulk_insert(session, User, user_data, batch_size=500)

# 5. 分析慢查询
slow_queries = optimizer.get_slow_queries(limit=5)
for query in slow_queries:
    print(f"Query: {query['statement'][:100]}, Time: {query['time']:.2f}s")
"""
