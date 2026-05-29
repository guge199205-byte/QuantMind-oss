import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services.engine.auth_context import get_authenticated_identity
from backend.services.engine.inference import InferenceRouterService, InferenceService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize service
inference_service = InferenceService()
inference_router_service = InferenceRouterService(inference_service=inference_service)


# Request/Response Models


class PredictionRequest(BaseModel):
    model_id: str | None = None
    strategy_id: str | None = None
    data: dict[str, Any] | list[dict[str, Any]]
    model_config = {"protected_namespaces": ()}


class ModelLoadRequest(BaseModel):
    model_id: str
    model_config = {"protected_namespaces": ()}


class PredictionResponse(BaseModel):
    status: str
    model_id: str | None = None
    predictions: list[float] | None = None
    input_shape: tuple | None = None
    symbols: list[str] | None = None
    fallback_used: bool | None = None
    fallback_reason: str | None = None
    active_model_id: str | None = None
    effective_model_id: str | None = None
    model_source: str | None = None
    active_data_source: str | None = None
    error: str | None = None
    model_config = {"protected_namespaces": ()}


class ModelInfo(BaseModel):
    status: str
    model_id: str
    metadata: dict[str, Any] | None = None
    error: str | None = None
    model_config = {"protected_namespaces": ()}


@router.get("/models")
async def list_models():
    """List all available models."""
    try:
        models = inference_service.list_models()
        return {"status": "success", "count": len(models), "models": models}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model_info(model_id: str):
    """Get detailed information about a specific model."""
    try:
        info = inference_service.get_model_info(model_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        return {"status": "success", "model": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/load")
async def load_model(request: ModelLoadRequest) -> ModelInfo:
    """Load a model into memory."""
    try:
        result = inference_service.load_model(request.model_id)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to load model"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/models/{model_id}")
async def unload_model(model_id: str):
    """Unload a model from memory."""
    try:
        result = inference_service.unload_model(model_id)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to unload model"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unload model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict(request: PredictionRequest, http_request: Request) -> PredictionResponse:
    """Generate prediction using a loaded model."""
    trace_id = f"predict_{uuid.uuid4().hex[:12]}"
    try:
        auth_user_id, auth_tenant_id = get_authenticated_identity(http_request)
        result = await inference_router_service.predict_with_fallback_async(
            request.model_id or "",
            request.data,
            tenant_id=auth_tenant_id,
            user_id=auth_user_id,
            strategy_id=request.strategy_id,
            trace_id=trace_id,
        )
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Prediction failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Prediction failed, trace_id=%s error=%s", trace_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buffer/stats")
async def buffer_stats():
    """Get history buffer statistics for monitoring."""
    try:
        stats = inference_service.get_buffer_stats()
        return {"status": "success", "buffer": stats}
    except Exception as e:
        logger.error(f"Failed to get buffer stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
