"""Qlib 回测服务"""

import asyncio
import json
import logging
import os
import random
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.services.engine.qlib_app.schemas.backtest import (
    QlibBacktestRequest,
    QlibBacktestResult,
)
from backend.services.engine.qlib_app.services.backtest_persistence import (
    BacktestPersistence,
)
from backend.services.engine.qlib_app.services.market_state_service import (
    MarketStateService,
)
from backend.services.engine.qlib_app.services.risk_analyzer import RiskAnalyzer
from backend.services.engine.qlib_app.services.strategy_builder import StrategyFactory
from backend.services.engine.qlib_app.services.strategy_templates import get_template_by_id
from backend.services.engine.qlib_app.utils.margin_position import ensure_margin_backtest_support
from backend.services.engine.qlib_app.utils.qlib_utils import (
    QLIB_BACKEND,
    D,
    backtest,
    exclude_bj_instruments,
    qlib,
)
from backend.services.engine.qlib_app.utils.strategy_adapter import StrategyAdapter
from backend.shared.notification_publisher import publish_notification_async
from backend.shared.utils import normalize_user_id
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger
from .backtest_service_runtime import QlibBacktestServiceRuntimeMixin

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "BacktestService")


# 计算项目根目录
def _find_project_root() -> Path:
    try:
        curr = Path(__file__).resolve().parent
        for _ in range(10):
            if (curr / "GEMINI.md").exists() or (curr / "requirements.txt").exists():
                return curr
            if curr.parent == curr:
                break
            curr = curr.parent
    except Exception:
        pass
    return Path(os.getcwd())


PROJECT_ROOT = _find_project_root()
task_logger.info("project_root_resolved", "Project root resolved", root=str(PROJECT_ROOT))


class QlibBacktestService(QlibBacktestServiceRuntimeMixin):
    """Qlib 回测服务"""

    def __init__(
        self,
        provider_uri: str | None = None,
        region: str = "cn",
    ):
        if provider_uri is None:
            provider_uri = os.getenv("QLIB_DATA_PATH", "db/qlib_data")

        if not provider_uri.startswith("~") and not os.path.isabs(provider_uri):
            try:
                potential_path = PROJECT_ROOT / provider_uri
                if potential_path.exists():
                    provider_uri = str(potential_path)
                    task_logger.info("provider_uri_resolved", "Resolved provider_uri", provider_uri=provider_uri)
            except Exception:
                pass

        self.provider_uri = provider_uri
        self.region = region
        self._initialized = False
        self._runs: dict[str, dict[str, Any]] = {}
        self._persistence = BacktestPersistence()
        self._seed = self._load_seed()
        self._kernels = self._load_kernels()
        self._joblib_backend = self._load_joblib_backend()
        self._adapter = StrategyAdapter(PROJECT_ROOT)
        self._market_state_service = MarketStateService()

        from backend.services.engine.qlib_app.cache_manager import get_cache_manager

        try:
            self._cache = get_cache_manager()
            task_logger.info("cache_manager_initialized", "缓存管理器已初始化")
        except Exception as e:
            task_logger.warning("cache_manager_init_failed", "缓存管理器初始化失败，将不使用缓存", error=str(e))
            self._cache = None

    def _load_seed(self) -> int | None:
        seed = os.getenv("QLIB_BACKTEST_SEED")
        if not seed:
            return None
        try:
            return int(seed)
        except ValueError:
            task_logger.warning("invalid_seed", "Invalid QLIB_BACKTEST_SEED", seed=seed)
            return None

    def _load_kernels(self) -> int:
        raw = os.getenv("QLIB_BACKTEST_KERNELS")
        if raw:
            try:
                value = int(raw)
                if value > 0:
                    return value
            except ValueError:
                task_logger.warning("invalid_kernels", "Invalid QLIB_BACKTEST_KERNELS", value=raw)
        return max(1, min((os.cpu_count() or 1), 8))

    def _load_joblib_backend(self) -> str:
        backend = os.getenv("QLIB_JOBLIB_BACKEND")
        if backend:
            return backend.strip()
        return "threading" if os.name == "nt" else "loky"

    def _set_deterministic_seed(self, seed: int | None) -> None:
        if seed is None:
            return
        random.seed(seed)
        np.random.seed(seed)
        try:
            import torch

            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        except Exception:
            pass

    def _resolve_seed(self, request_seed: int | None) -> int | None:
        return request_seed if request_seed is not None else self._seed

    @staticmethod
    def _should_enable_short_selling(request: QlibBacktestRequest) -> bool:
        return str(request.strategy_type or "").strip().lower() == "long_short_topk" and bool(
            request.strategy_params.enable_short_selling
        )

    @staticmethod
    def _resolve_strategy_builder(request: QlibBacktestRequest):
        """
        解析策略 Builder。
        优先使用内置映射；若未命中且存在同 ID 模板，则自动回退到模板代码执行。
        """
        builder, is_fallback, normalized = StrategyFactory.resolve_builder(request.strategy_type)
        if not is_fallback:
            return builder

        if request.strategy_content and request.strategy_content.strip():
            return StrategyFactory.get_builder("CustomStrategy")

        template = get_template_by_id(request.strategy_type) or get_template_by_id(normalized)
        if template and getattr(template, "code", "").strip():
            request.strategy_content = template.code
            request.strategy_type = "CustomStrategy"
            task_logger.info(
                "strategy_template_matched",
                "Unknown strategy_type matched template",
                strategy_type=normalized,
                template_id=template.id,
            )
            return StrategyFactory.get_builder("CustomStrategy")

        task_logger.warning(
            "strategy_template_not_found",
            "Unknown strategy_type not found in template directory, keep TopkDropout fallback",
            strategy_type=normalized,
        )
        return builder

    def _build_strategy_from_content(self, content: str):
        """
        兼容旧单测入口：从策略代码构建策略实例。
        """
        namespace: dict[str, Any] = {}
        exec(content, namespace)

        if callable(namespace.get("get_strategy_instance")):
            return namespace["get_strategy_instance"]()

        for value in namespace.values():
            if isinstance(value, type):
                try:
                    return value()
                except Exception:
                    continue

        raise ValueError("策略代码未提供可实例化对象")

    def initialize(self):
        """初始化 Qlib 并进行数据完整性预检"""
        if not self._initialized:
            try:
                qlib.init(
                    provider_uri=self.provider_uri,
                    region=self.region,
                    joblib_backend=self._joblib_backend,
                )
                from qlib.config import C

                C["joblib_backend"] = self._joblib_backend
                C["kernels"] = self._kernels
                self._initialized = True
                task_logger.info(
                    "qlib_initialized",
                    "Qlib 初始化成功",
                    provider_uri=self.provider_uri,
                    region=self.region,
                    joblib_backend=self._joblib_backend,
                    kernels=self._kernels,
                )
                self._audit_data_quality()
            except Exception as e:
                task_logger.error("qlib_init_failed", "Qlib 初始化失败", error=str(e))
                raise

    def _audit_data_quality(self):
        """轻量级数据质量审计 — 已禁用，避免 D.features() 在容器内触发 CPU 死循环"""
        pass

    def check_health(self) -> dict[str, Any]:
        """健康检查（不触发初始化，避免 qlib.init 卡死导致健康检查也卡住）"""
        try:
            return {
                "status": "healthy" if self._initialized else "degraded",
                "qlib_initialized": self._initialized,
                "version": qlib.__version__,
                "data_available": False,
                "qlib_backend": QLIB_BACKEND,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "qlib_initialized": False,
                "version": "unknown",
                "data_available": False,
                "qlib_backend": QLIB_BACKEND,
                "error": str(e),
            }

# 全局服务实例
qlib_service: QlibBacktestService = None  # type: ignore
