import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from redis import Redis

from backend.shared.redis_sentinel_client import get_redis_sentinel_client

logger = logging.getLogger(__name__)

# Runner 消费的 signal stream 前缀（与 runner/main.py 保持一致）
_SIGNAL_STREAM_PREFIX = "qm:signal:stream"
_SIGNAL_LATEST_PREFIX = "qm:signal:latest"
_SIGNAL_STREAM_MAXLEN = 200000


class VectorizedMatcher:
    """
    向量化匹配引擎 (Vectorized Matcher)
    定位：支撑 10 万并发的核心决策组件。
    原理：监听全局信号更新，批量加载用户策略配置，通过 pandas 向量化运算瞬间算出 10 万人的下单指令。

    Redis 路由说明：
    - self.redis (sentinel_redis): 读取 alpha_scores、active_strategies，订阅 signal_updated 事件。
      使用 REDIS_HOST 环境变量。引擎服务中该变量指向 backtest-redis。
    - self._stream_redis: 写入 qm:signal:stream，与 runner 消费的 Redis 保持一致。
      优先使用 SIGNAL_STREAM_REDIS_HOST 环境变量（默认回退至 sentinel_redis）。
      交易服务（runner）中 REDIS_HOST 指向 trade-redis，因此需独立客户端隔离。
    """

    STRATEGIES_HASH_KEY = "quantmind:active_strategies"
    SIGNAL_KEY = "quantmind:global:alpha_scores"
    SIGNAL_EVENT_CHANNEL = "quantmind:events:signal_updated"

    def __init__(self):
        self.redis = get_redis_sentinel_client()
        self._stream_redis: Redis | None = None
        self.is_running = False

    def _get_stream_client(self) -> Any:
        """
        获取写入信号流的 Redis 客户端。
        优先使用 SIGNAL_STREAM_REDIS_HOST（trade-redis），保证与 runner 读同一实例。
        未配置时回退为 sentinel_redis（适用于单 Redis 开发环境）。
        """
        if self._stream_redis is not None:
            return self._stream_redis

        stream_host = str(os.getenv("SIGNAL_STREAM_REDIS_HOST", "")).strip()
        if stream_host:
            self._stream_redis = Redis(
                host=stream_host,
                port=int(os.getenv("SIGNAL_STREAM_REDIS_PORT", "6379")),
                db=int(os.getenv("SIGNAL_STREAM_REDIS_DB", "0")),
                password=os.getenv("SIGNAL_STREAM_REDIS_PASSWORD") or None,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                health_check_interval=30,
            )
            return self._stream_redis
        # 单 Redis 环境（本地开发）回退
        return self.redis

    async def start(self):
        """
        启动监听循环。受 ENABLE_VECTORIZED_MATCHER 环境变量控制（默认 false）。
        """
        enabled = os.getenv("ENABLE_VECTORIZED_MATCHER", "false").lower() in {"1", "true", "yes", "on"}
        if not enabled:
            logger.info("[VectorizedMatcher] 未启用（ENABLE_VECTORIZED_MATCHER 未设置），跳过。")
            return

        self.is_running = True
        # pubsub.subscribe/get_message 是同步调用，必须通过 to_thread 避免阻塞事件循环
        pubsub = self.redis.pubsub()
        await asyncio.to_thread(pubsub.subscribe, self.SIGNAL_EVENT_CHANNEL)

        logger.info("[VectorizedMatcher] 已启动，监听频道: %s", self.SIGNAL_EVENT_CHANNEL)

        try:
            while self.is_running:
                message = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_defaults=True, timeout=1.0)
                if message and message["type"] == "message":
                    event_data = json.loads(message["data"])
                    logger.info("[VectorizedMatcher] 收到信号更新通知: %s", event_data)
                    await self.run_bulk_match()

                await self._consume_sandbox_signals()
                await asyncio.sleep(0.1)
        finally:
            await asyncio.to_thread(pubsub.unsubscribe, self.SIGNAL_EVENT_CHANNEL)
            logger.info("[VectorizedMatcher] 已停止。")

    async def run_bulk_match(self):
        """
        核心矩阵匹配逻辑：读取全局 alpha scores，为每个活跃策略选出 TopK 标的，
        写入各 tenant 的 Runner 信号流（trade-redis）。

        补充路径（Fallback）语义：
        - 优先检查 trade-redis 上 qm:signal:latest:{tenant_id}:{user_id} 是否存在。
        - 若存在，说明 EngineSignalStreamPublisher 今日已为该用户发布了个性化信号，跳过。
        - 若不存在，代表该用户无个性化推理结果，由此处补充全局 TopK 信号作为兜底。
        """
        loop = asyncio.get_event_loop()
        start_time = loop.time()

        # 1. 批量加载全量信号 (Alpha Scores) — 从 sentinel_redis (backtest-redis) 读取
        raw_signals = self.redis.get(self.SIGNAL_KEY)
        if not raw_signals:
            logger.warning("[VectorizedMatcher] 未找到全局信号，跳过匹配")
            return

        scores_dict = json.loads(raw_signals)
        s_scores = pd.Series(scores_dict)

        # 2. 批量加载所有活跃策略配置 — 从 sentinel_redis 读取
        all_strategies_raw = self.redis.hgetall(self.STRATEGIES_HASH_KEY)
        if not all_strategies_raw:
            logger.info("[VectorizedMatcher] 当前无活跃策略，等待配置下发...")
            return

        stream_client = self._get_stream_client()

        # 3. 构造计算矩阵：为每个策略选出 TopK，按 tenant 分组写入 Runner 信号流
        run_id = f"vm-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        stream_events: dict[str, list] = {}  # tenant_id -> list of flat field dicts
        latest_users: dict[str, set] = {}
        fallback_count = 0
        skipped_count = 0

        for strategy_id, config_json in all_strategies_raw.items():
            try:
                config = json.loads(config_json)
                topk = int(config.get("topk") or 5)
                universe = config.get("universe", [])
                user_id = str(config.get("user_id") or "")
                tenant_id = str(config.get("tenant_id") or "default")

                if not user_id:
                    continue

                # 补充路径核心：若 EngineSignalStreamPublisher 已为该用户发布信号，跳过
                latest_key = f"{_SIGNAL_LATEST_PREFIX}:{tenant_id}:{user_id}"
                if stream_client.exists(latest_key):
                    skipped_count += 1
                    continue  # 个性化推理已覆盖，无需全局兜底

                latest_users.setdefault(tenant_id, set()).add(user_id)
                fallback_count += 1

                pool_scores = s_scores[s_scores.index.isin(universe)] if universe else s_scores
                selected = pool_scores.nlargest(topk)

                tenant_events = stream_events.setdefault(tenant_id, [])
                for idx, (symbol, score) in enumerate(selected.items()):
                    signal_id = f"{run_id}-{strategy_id}-{idx:04d}"
                    tenant_events.append(
                        {
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "batch_id": run_id,
                            "run_id": run_id,
                            "trace_id": run_id,
                            "signal_id": signal_id,
                            "client_order_id": f"coid-{signal_id}",
                            "symbol": str(symbol).upper(),
                            "side": "BUY",
                            "quantity": str(int(config.get("order_quantity") or 100)),
                            "price": "0.0",
                            "score": str(round(float(score), 6)),
                            "signal_source": "vectorized_matcher_fallback",
                        }
                    )
            except Exception as e:
                logger.error("[VectorizedMatcher] 解析策略 %s 失败: %s", strategy_id, e)

        logger.info(
            "[VectorizedMatcher] 策略扫描完成: 总=%d 跳过(已有推理)=%d 兜底=%d",
            len(all_strategies_raw), skipped_count, fallback_count,
        )

        if not stream_events:
            return  # 所有用户都有个性化推理，无需兜底

        # 4. 批量写入各 tenant 的 Runner 信号流（使用 trade-redis stream client）
        total_published = 0
        pipeline = stream_client.pipeline()
        # 写入 latest run key，Runner 用它校验信号时效性
        for tenant_id, users in latest_users.items():
            for user_id in users:
                pipeline.set(f"{_SIGNAL_LATEST_PREFIX}:{tenant_id}:{user_id}", run_id, ex=86400)
        for tenant_id, events in stream_events.items():
            stream = f"{_SIGNAL_STREAM_PREFIX}:{tenant_id}"
            for event in events:
                pipeline.xadd(stream, event, maxlen=_SIGNAL_STREAM_MAXLEN, approximate=True)
                total_published += 1
        if total_published:
            pipeline.execute()
            elapsed = loop.time() - start_time
            logger.info(
                "[VectorizedMatcher] 批量匹配完成: 产生 %d 笔信号事件, 耗时 %.3fs, run_id=%s",
                total_published, elapsed, run_id,
            )

    async def _consume_sandbox_signals(self):
        """监控沙箱信号队列状态（只读探针，不消费信号）"""
        try:
            # 使用 LLEN 获取队列长度而非 LPOP 消费信号
            queue_len = self.redis.llen("trade:simulation:signals")
            if queue_len > 0:
                logger.debug(
                    "[VectorizedMatcher] 沙箱信号队列待消费: %d 条",
                    queue_len,
                )
        except Exception as e:
            logger.error("[VectorizedMatcher] Error probing sandbox signals: %s", e)

    def stop(self):
        self.is_running = False
        if self._stream_redis is not None:
            try:
                self._stream_redis.close()
            except Exception:
                pass
            self._stream_redis = None


# 单例
vectorized_matcher = VectorizedMatcher()
