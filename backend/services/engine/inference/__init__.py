"""
Inference module - migrated from backend.ai_inference.
Provides real-time model inference capabilities for Qlib models.
"""

from .service import InferenceService
from .router_service import InferenceRouterService

__all__ = ["InferenceService", "InferenceRouterService"]
