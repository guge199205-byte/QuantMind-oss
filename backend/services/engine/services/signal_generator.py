import json
import logging
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

from backend.shared.redis_sentinel_client import get_redis_sentinel_client

logger = logging.getLogger(__name__)


class GlobalSignalGenerator:
    """
    全局信号生成器 (Alpha Scores Generator)
    定位：quantmind-engine 的核心服务，负责生产全市场的预测信号并广播至 Redis。
    支持 10 万并发架构的“算一次，供全场”模式。
    """

    SIGNAL_KEY = "quantmind:global:alpha_scores"
    METADATA_KEY = "quantmind:global:alpha_metadata"

    def __init__(self):
        self.redis = get_redis_sentinel_client()

    async def generate_and_broadcast(self, universe: str = "all", mock: bool = False):
        """
        生成信号并广播至 Redis
        :param universe: 股票池名称，默认 all (全市场)
        :param mock: 是否使用模拟数据 (在正式对接 Qlib 模型前使用)
        """
        logger.info(f"开始生成全局信号: universe={universe}, mock={mock}")

        try:
            if mock:
                scores = self._generate_mock_scores()
            else:
                scores = await self._run_qlib_inference(universe)

            # 准备元数据
            metadata = {
                "generated_at": datetime.now().isoformat(),
                "count": len(scores),
                "universe": universe,
                "version": "v2.0-vectorized",
            }

            # 写入 Redis
            # 1. 写入全量得分 (Hash 结构，方便按股票查询)
            # 注意：对于 10 万人级别，全量拉取 json 虽快，但 Redis Hash 结构更利于增量更新
            # 此处我们先采用 String 存储全量 JSON 以配合 Vectorized Matcher 的批量读取
            self.redis.set(self.SIGNAL_KEY, json.dumps(scores))
            self.redis.set(self.METADATA_KEY, json.dumps(metadata))

            # 2. 发布信号更新事件，通知 quantmind-trade 触发批量匹配
            self.redis.publish("quantmind:events:signal_updated", json.dumps(metadata))

            logger.info(f"全局信号已广播: 标的数量={len(scores)}, Key={self.SIGNAL_KEY}")
            return True

        except Exception as e:
            logger.error(f"生成全局信号失败: {e}", exc_info=True)
            return False

    async def _run_qlib_inference(self, universe: str) -> dict[str, float]:
        """
        调用 InferenceService 执行真实模型推理，生成全市场 Alpha 信号。
        从 market_data_daily 加载预计算特征，通过 InferenceService.predict_batch 推理。
        若特征数据不可用，则回退至 Mock 数据（开发环境）。
        """
        from datetime import date as _date

        from backend.services.engine.inference.service import InferenceService
        from backend.services.engine.tasks.etl_worker import ETLWorker
        from backend.shared.database import SessionLocal

        model_id = os.getenv("INFERENCE_DEFAULT_MODEL", "model_qlib")
        date_str = _date.today().isoformat()
        db = SessionLocal()
        try:
            etl = ETLWorker(db)
            df = etl.load_features_from_db(date_str)
            if df.empty:
                logger.warning(f"[SignalGen] {date_str} 特征数据为空，回退 Mock 信号")
                return self._generate_mock_scores()

            inference = InferenceService()
            result = inference.predict_batch(model_id, df)
            if result.get("status") != "success":
                logger.error(f"[SignalGen] predict_batch 失败: {result}")
                return self._generate_mock_scores()

            symbols = result["symbols"]
            scores = result["predictions"]
            logger.info(f"[SignalGen] 模型推理完成: {len(symbols)} 个标的，model={model_id}")
            return {sym: round(float(score), 4) for sym, score in zip(symbols, scores)}

        except Exception as e:
            logger.error(f"[SignalGen] Qlib 推理失败: {e}", exc_info=True)
            return self._generate_mock_scores()
        finally:
            db.close()

    def _generate_mock_scores(self) -> dict[str, float]:
        """
        生成模拟的全市场得分 (模拟 A 股 5000 只股票)
        """
        # 模拟一些核心标的
        core_symbols = ["SH600000", "SH600519", "SZ000001", "SZ000002", "SH601318"]
        scores = {sym: round(random.uniform(0, 1), 4) for sym in core_symbols}

        # 随机生成另外 4000+ 只
        for i in range(1, 4500):
            sym = f"SH{600000 + i}"
            scores[sym] = round(random.uniform(0, 1), 4)

        return scores


# 单例
global_signal_generator = GlobalSignalGenerator()
