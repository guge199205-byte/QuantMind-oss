"""Background thread runner for TradingAgentsGraph pipeline."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from typing import Any

from backend.services.engine.trading_agents.progress import (
    PIPELINE_STAGES,
    ProgressTracker,
    STAGE_IDS,
)

logger = logging.getLogger(__name__)


def _save_to_database(
    analysis_id: str,
    ticker: str,
    trade_date: str,
    signal: str,
    config: dict,
    tracker: ProgressTracker,
    final_state: dict[str, Any],
    error: str | None = None,
) -> None:
    """Persist analysis results to PostgreSQL (sync, called from worker thread)."""
    try:
        import os
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker

        db_url = os.getenv("DATABASE_URL", "").strip()
        if not db_url:
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "5432")
            user = os.getenv("DB_USER", "quantmind")
            password = os.getenv("DB_PASSWORD", "quantmind2026")
            db_name = os.getenv("DB_NAME", "quantmind")
            db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
        elif "asyncpg" in db_url:
            db_url = db_url.replace("asyncpg", "psycopg2")

        engine = create_engine(db_url, pool_size=2, max_overflow=2)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Sanitize final_state: remove non-serializable objects
        clean_final = {}
        for k, v in (final_state or {}).items():
            try:
                json.dumps(v, ensure_ascii=False)
                clean_final[k] = v
            except (TypeError, ValueError):
                clean_final[k] = str(v)[:2000] if v else None

        session.execute(
            text("""
                INSERT INTO qm_trading_agents_history
                    (analysis_id, ticker, trade_date, signal,
                     llm_provider, deep_think_llm, quick_think_llm,
                     stage_reports, final_state, stats, elapsed_seconds, error,
                     created_at, updated_at)
                VALUES
                    (:aid, :ticker, :td, :signal,
                     :provider, :deep, :quick,
                     :reports, :final, :stats, :elapsed, :error,
                     NOW(), NOW())
                ON CONFLICT (analysis_id) DO UPDATE SET
                    signal = EXCLUDED.signal,
                    stage_reports = EXCLUDED.stage_reports,
                    final_state = EXCLUDED.final_state,
                    stats = EXCLUDED.stats,
                    elapsed_seconds = EXCLUDED.elapsed_seconds,
                    error = EXCLUDED.error,
                    updated_at = NOW()
            """),
            {
                "aid": analysis_id,
                "ticker": ticker,
                "td": trade_date,
                "signal": signal or "",
                "provider": config.get("llm_provider", ""),
                "deep": config.get("deep_think_llm", ""),
                "quick": config.get("quick_think_llm", ""),
                "reports": json.dumps(tracker.stage_reports, ensure_ascii=False),
                "final": json.dumps(clean_final, ensure_ascii=False),
                "stats": json.dumps({
                    "llm_calls": tracker.llm_calls,
                    "tool_calls": tracker.tool_calls,
                    "tokens_in": tracker.tokens_in,
                    "tokens_out": tracker.tokens_out,
                }, ensure_ascii=False),
                "elapsed": tracker.elapsed,
                "error": error,
            },
        )
        session.commit()
        session.close()
        engine.dispose()
        logger.info("Saved analysis %s to database", analysis_id)
    except Exception as e:
        logger.warning("Failed to save analysis to database: %s", e)

_REPORT_KEY_TO_STAGE = {s["report_key"]: s["id"] for s in PIPELINE_STAGES}

_ANALYST_REPORT_KEYS = [
    "market_report", "sentiment_report", "news_report",
    "fundamentals_report", "policy_report", "hot_money_report", "lockup_report",
]


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _detect_completed_stages(
    chunk: dict[str, Any],
    tracker: ProgressTracker,
) -> None:
    """Check the streamed chunk for newly completed stages."""
    for report_key in _ANALYST_REPORT_KEYS:
        stage_id = _REPORT_KEY_TO_STAGE[report_key]
        content = chunk.get(report_key, "")
        if content and tracker.stage_status(stage_id) != "done":
            tracker.mark_stage_done(stage_id, _strip_think_tags(str(content)))

    dqs = chunk.get("data_quality_summary", "")
    if dqs and tracker.stage_status("quality_gate") != "done":
        tracker.mark_stage_done("quality_gate", str(dqs))

    debate = chunk.get("investment_debate_state")
    if debate and isinstance(debate, dict):
        judge = debate.get("judge_decision", "")
        if judge and tracker.stage_status("debate") != "done":
            tracker.mark_stage_done("debate", str(judge))

    trader_plan = chunk.get("trader_investment_plan", "")
    if trader_plan and tracker.stage_status("trader") != "done":
        tracker.mark_stage_done("trader", _strip_think_tags(str(trader_plan)))

    risk = chunk.get("risk_debate_state")
    if risk and isinstance(risk, dict):
        risk_judge = risk.get("judge_decision", "")
        if risk_judge and tracker.stage_status("risk") != "done":
            tracker.mark_stage_done("risk", str(risk_judge))

    final = chunk.get("final_trade_decision", "")
    if final and tracker.stage_status("pm") != "done":
        tracker.mark_stage_done("pm", _strip_think_tags(str(final)))


def _infer_active_stage(tracker: ProgressTracker) -> None:
    """Set the current_stage to the first non-completed stage."""
    for sid in STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _run(ticker: str, trade_date: str, config: dict, tracker: ProgressTracker, analysis_id: str = "") -> None:
    """Execute the full pipeline in the current thread."""
    try:
        from cli.stats_handler import StatsCallbackHandler
        from tradingagents.graph.trading_graph import TradingAgentsGraph
    except ImportError as e:
        raise RuntimeError(
            f"TradingAgents package not installed: {e}. "
            "Install with: pip install -e /app/TradingAgents-astock"
        ) from e

    stats = StatsCallbackHandler()

    graph = TradingAgentsGraph(
        debug=True,
        config=config,
        callbacks=[stats],
    )

    init_state = graph.propagator.create_initial_state(ticker, trade_date)
    args = graph.propagator.get_graph_args(callbacks=[stats])

    last_chunk: dict[str, Any] = {}

    for chunk in graph.graph.stream(init_state, **args):
        last_chunk = chunk
        _detect_completed_stages(chunk, tracker)
        _infer_active_stage(tracker)

        s = stats.get_stats()
        tracker.update_stats(s["llm_calls"], s["tool_calls"], s["tokens_in"], s["tokens_out"])

    signal = graph.process_signal(last_chunk.get("final_trade_decision", ""))

    graph.ticker = ticker
    try:
        graph._log_state(trade_date, last_chunk)
    except Exception as e:
        logger.warning("Failed to log state to disk (non-fatal): %s", e)

    tracker.mark_complete(last_chunk, signal)

    # Persist to database
    if analysis_id:
        _save_to_database(analysis_id, ticker, trade_date, signal, config, tracker, last_chunk)


def run_analysis_in_thread(
    ticker: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
    analysis_id: str = "",
) -> threading.Thread:
    """Launch the pipeline in a daemon thread. Returns the thread handle."""
    tracker.ticker = ticker
    tracker.trade_date = trade_date
    tracker.is_running = True
    tracker.mark_stage_active("market")

    def _target() -> None:
        try:
            _run(ticker, trade_date, config, tracker, analysis_id=analysis_id)
        except Exception as exc:
            logger.exception("TradingAgents pipeline failed for %s", ticker)
            tracker.mark_error(str(exc))
            # Save error state to database
            if analysis_id:
                _save_to_database(
                    analysis_id, ticker, trade_date, "", config, tracker, {},
                    error=str(exc),
                )

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t
