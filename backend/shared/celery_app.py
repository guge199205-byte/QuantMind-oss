"""
Celery异步任务配置
"""

import os

from celery import Celery
from celery.schedules import crontab


def _build_redis_url(db_index: int) -> str:
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "")
    if password:
        return f"redis://:{password}@{host}:{port}/{db_index}"
    return f"redis://{host}:{port}/{db_index}"


# Celery配置
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    _build_redis_url(int(os.getenv("REDIS_DB_BROKER", "1"))),
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    _build_redis_url(int(os.getenv("REDIS_DB_BACKEND", "2"))),
)

# 创建Celery应用
celery_app = Celery(
    "quantmind",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.stock_tasks",
        "backend.tasks.backtest_tasks",
        "backend.tasks.ai_tasks",
        "backend.tasks.maintenance_tasks",
    ],
)

# Celery配置
celery_app.conf.update(
    # 任务序列化格式
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务执行配置
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟
    task_soft_time_limit=25 * 60,  # 25分钟
    # 工作进程配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # 结果配置
    result_expires=3600,  # 1小时
    # 重试配置
    task_acks_late=True,
    worker_disable_rate_limits=False,
    # 定时任务配置
    beat_schedule={
        "sync-stock-data-daily": {
            "task": "backend.tasks.stock_tasks.sync_stock_data",
            "schedule": crontab(hour=9, minute=0),  # 每天9点同步
        },
        "sync-stock-data-weekly": {
            "task": "backend.tasks.stock_tasks.sync_stock_data_full",
            "schedule": crontab(day_of_week=1, hour=2, minute=0),  # 每周一2点全量同步
        },
        "cleanup-old-data": {
            "task": "backend.tasks.maintenance_tasks.cleanup_old_data",
            "schedule": crontab(hour=2, minute=0),  # 每天2点清理
        },
        "backup-database": {
            "task": "backend.tasks.maintenance_tasks.backup_database",
            "schedule": crontab(hour=3, minute=0),  # 每天3点备份
        },
        "warmup-cache": {
            "task": "backend.tasks.maintenance_tasks.warmup_cache",
            "schedule": crontab(minute="*/30"),  # 每30分钟预热缓存
        },
        "health-check": {
            "task": "backend.tasks.maintenance_tasks.health_check",
            "schedule": crontab(minute="*/5"),  # 每5分钟健康检查
        },
        "warmup-stock-latest-cache-daily": {
            "task": "engine.tasks.warmup_stock_latest_cache",
            "schedule": crontab(hour=22, minute=30, day_of_week="1-5"),  # 交易日 22:30 预热最新行情缓存
        },
    },
)

# 任务路由
celery_app.conf.task_routes = {
    "backend.tasks.stock_tasks.*": {"queue": "stock"},
    "backend.tasks.backtest_tasks.*": {"queue": "backtest"},
    "backend.tasks.ai_tasks.*": {"queue": "ai"},
    "backend.tasks.maintenance_tasks.*": {"queue": "maintenance"},
}

# 队列配置
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

if __name__ == "__main__":
    celery_app.start()
