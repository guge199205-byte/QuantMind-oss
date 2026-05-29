from fastapi import APIRouter
import logging
from .internal_strategy_bridge import router as bridge_router
from .internal_strategy_lifecycle import router as lifecycle_router

router = APIRouter(prefix="/api/v1/internal/strategy", tags=["Internal Strategy Gateway"])
logger = logging.getLogger(__name__)

router.include_router(bridge_router)
router.include_router(lifecycle_router)
