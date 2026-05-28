"""TradingAgents REST API — analyze, progress, report, history."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trading-agents", tags=["TradingAgents"])

# In-memory tracker registry (keyed by analysis_id)
_trackers: dict[str, object] = {}
_threads: dict[str, object] = {}

# Results storage directory
_RESULTS_DIR = Path("/app/db/trading_agents_results")


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="A股代码，如 300750")
    trade_date: str = Field(default_factory=lambda: date.today().isoformat(), description="分析日期 YYYY-MM-DD")
    llm_provider: str = Field(default="minimax", description="LLM 供应商")
    deep_think_llm: str = Field(default="MiniMax-M2.7", description="深度思考模型")
    quick_think_llm: str = Field(default="MiniMax-M2.7-highspeed", description="快速思考模型")


class StopRequest(BaseModel):
    analysis_id: str


def _build_config(req: AnalyzeRequest) -> dict:
    """Build TradingAgents config from request params."""
    try:
        from tradingagents.default_config import DEFAULT_CONFIG
        config = DEFAULT_CONFIG.copy()
    except ImportError:
        # Fallback config when TradingAgents is not installed
        config = {
            "llm_provider": "openai",
            "deep_think_llm": "gpt-5.4",
            "quick_think_llm": "gpt-5.4-mini",
            "backend_url": None,
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "data_cache_dir": "/app/db/trading_agents_cache",
            "results_dir": "/app/db/trading_agents_results",
        }

    config["llm_provider"] = req.llm_provider
    config["deep_think_llm"] = req.deep_think_llm
    config["quick_think_llm"] = req.quick_think_llm
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["output_language"] = "Chinese"
    return config


@router.post("/analyze")
async def start_analysis(req: AnalyzeRequest):
    """Start a new TradingAgents analysis."""
    from backend.services.engine.trading_agents.progress import ProgressTracker
    from backend.services.engine.trading_agents.runner import run_analysis_in_thread

    analysis_id = str(uuid.uuid4())[:8]

    config = _build_config(req)
    tracker = ProgressTracker()
    _trackers[analysis_id] = tracker

    thread = run_analysis_in_thread(
        ticker=req.ticker,
        trade_date=req.trade_date,
        config=config,
        tracker=tracker,
    )
    _threads[analysis_id] = thread

    return {
        "code": 200,
        "data": {
            "analysis_id": analysis_id,
            "ticker": req.ticker,
            "trade_date": req.trade_date,
            "message": "分析已启动",
        },
    }


@router.get("/progress/{analysis_id}")
async def get_progress(analysis_id: str):
    """Get current progress of an analysis."""
    tracker = _trackers.get(analysis_id)
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return {"code": 200, "data": tracker.to_dict()}


@router.get("/report/{analysis_id}")
async def get_report(analysis_id: str):
    """Get the full report of a completed analysis."""
    tracker = _trackers.get(analysis_id)
    if not tracker:
        # Try loading from disk
        return await _load_report_from_disk(analysis_id)

    if tracker.is_running:
        return {"code": 202, "data": {"message": "分析仍在进行中", "progress": tracker.to_dict()}}

    if tracker.error:
        return {"code": 500, "data": {"error": tracker.error}}

    return {
        "code": 200,
        "data": {
            "ticker": tracker.ticker,
            "trade_date": tracker.trade_date,
            "signal": tracker.signal,
            "final_state": tracker.final_state,
            "stage_reports": tracker.stage_reports,
            "stats": {
                "llm_calls": tracker.llm_calls,
                "tool_calls": tracker.tool_calls,
                "tokens_in": tracker.tokens_in,
                "tokens_out": tracker.tokens_out,
            },
            "elapsed": tracker.elapsed,
        },
    }


async def _load_report_from_disk(analysis_id: str) -> dict:
    """Try to load a report from disk storage."""
    for path in _RESULTS_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("analysis_id") == analysis_id:
                return {"code": 200, "data": data}
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"Report {analysis_id} not found")


@router.get("/history")
async def list_history(
    limit: int = Query(20, ge=1, le=100),
):
    """List recent analysis history."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = []

    # From in-memory trackers
    for aid, tracker in _trackers.items():
        if tracker.is_complete:
            history.append({
                "analysis_id": aid,
                "ticker": tracker.ticker,
                "trade_date": tracker.trade_date,
                "signal": tracker.signal,
                "elapsed": tracker.elapsed,
                "source": "memory",
            })

    # From disk
    for path in sorted(_RESULTS_DIR.rglob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            history.append({
                "analysis_id": data.get("analysis_id", path.stem),
                "ticker": data.get("ticker", ""),
                "trade_date": data.get("trade_date", ""),
                "signal": data.get("signal", ""),
                "elapsed": data.get("elapsed", 0),
                "source": "disk",
            })
        except Exception:
            continue

    return {"code": 200, "data": {"history": history[:limit], "total": len(history)}}


@router.post("/stop")
async def stop_analysis(req: StopRequest):
    """Stop a running analysis (best-effort — daemon threads can't be killed)."""
    tracker = _trackers.get(req.analysis_id)
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Analysis {req.analysis_id} not found")
    if not tracker.is_running:
        return {"code": 200, "data": {"message": "分析已完成或未在运行"}}

    tracker.mark_error("用户手动停止")
    return {"code": 200, "data": {"message": "已发送停止信号"}}


@router.get("/config")
async def get_config():
    """Get available LLM providers and models."""
    try:
        from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
    except ImportError:
        # Fallback when TradingAgents is not installed
        MODEL_OPTIONS = {
            "minimax": {
                "quick": [("MiniMax-M2.7-highspeed", "MiniMax-M2.7-highspeed")],
                "deep": [("MiniMax-M2.7", "MiniMax-M2.7")],
            },
            "deepseek": {
                "quick": [("DeepSeek V3.2", "deepseek-chat")],
                "deep": [("DeepSeek V4 Pro", "deepseek-v4-pro")],
            },
            "openai": {
                "quick": [("GPT-5.4 Mini", "gpt-5.4-mini")],
                "deep": [("GPT-5.4", "gpt-5.4")],
            },
        }

    providers = []
    for provider_key, modes in MODEL_OPTIONS.items():
        providers.append({
            "key": provider_key,
            "quick_models": [{"label": label, "value": val} for label, val in modes.get("quick", [])],
            "deep_models": [{"label": label, "value": val} for label, val in modes.get("deep", [])],
        })

    return {"code": 200, "data": {"providers": providers}}
