import pytest

from backend.services.engine.ai_strategy.services.startup_health import (
    get_startup_health_report,
    run_startup_health_checks,
)


@pytest.mark.asyncio
async def test_startup_health_checks_fail_fast(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.provider_registry.get_provider",
        lambda: object(),
    )

    async def _boom():
        raise RuntimeError("embedding service unavailable")

    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.services.selection.vector_parser.get_strategy_vector_parser",
        _boom,
    )
    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.services.selection.schema_retriever.get_schema_retriever",
        _boom,
    )

    with pytest.raises(RuntimeError, match="startup health check failed"):
        await run_startup_health_checks(timeout_seconds=2)

    report = get_startup_health_report()
    assert report["ready"] is False
    assert report["vector_parser_ready"] is False
    assert report["schema_retriever_ready"] is False
    assert "embedding service unavailable" in report["error"]
