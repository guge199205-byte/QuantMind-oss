import asyncio
import json
import logging
import os
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import desc, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

import redis as redis_lib
from backend.services.trade.deps import AuthContext, get_auth_context, get_db
from backend.services.trade.models.order import Order
from backend.services.trade.models.preflight_snapshot import PreflightSnapshot
from backend.services.trade.portfolio.models import Portfolio
from backend.services.trade.models.trade import Trade
from backend.services.trade.redis_client import RedisClient, get_redis
from backend.services.trade.utils.redis_cache import redis_cache
from backend.services.trade.schemas.live_trade_config import (
    ExecutionConfigSchema,
    LiveTradeConfigSchema,
)
from backend.services.trade.services.k8s_manager import k8s_manager
from backend.services.trade.services.trading_precheck_service import (
    _check_inference_model_exists,
    run_trading_readiness_precheck,
)
from backend.services.trade.trade_config import settings
from backend.shared.margin_stock_pool import get_margin_stock_pool_service
from .real_trading_utils import *
from .real_trading_preflight import router as preflight_router
from .real_trading_ledger import router as ledger_router
from .manual_executions import router as manual_executions_router
from .real_trading_lifecycle import router as lifecycle_router

router = APIRouter()
logger = logging.getLogger(__name__)

router.include_router(preflight_router)
router.include_router(ledger_router)
router.include_router(manual_executions_router)
router.include_router(lifecycle_router)
