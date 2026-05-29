import pytest

from backend.services.engine.qlib_app.schemas.backtest import (
    OptimizationParamRange,
    QlibBacktestRequest,
    QlibBacktestResult,
    QlibOptimizationRequest,
    QlibStrategyParams,
)
from backend.services.engine.qlib_app.services.optimization_service import OptimizationService


class _FakeBacktestService:
    def __init__(self):
        self.calls = []

    async def run_backtest(self, request: QlibBacktestRequest) -> QlibBacktestResult:
        self.calls.append(
            (
                request.strategy_params.topk,
                request.strategy_params.n_drop,
                request.history_source,
            )
        )
        return QlibBacktestResult(
            backtest_id=f"{request.strategy_params.topk}-{request.strategy_params.n_drop}",
            status="completed",
            annual_return=float(request.strategy_params.topk) / 100,
            sharpe_ratio=float(request.strategy_params.topk + request.strategy_params.n_drop),
            max_drawdown=-0.1,
        )


@pytest.mark.asyncio
async def test_run_optimization_reports_incremental_progress():
    service = OptimizationService(_FakeBacktestService())
    request = QlibOptimizationRequest(
        base_request=QlibBacktestRequest(
            strategy_type="TopkDropout",
            strategy_params=QlibStrategyParams(topk=20, n_drop=1),
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=1_000_000,
            user_id="00000001",
            tenant_id="default",
        ),
        param_ranges=[
            OptimizationParamRange(name="topk", min=20, max=30, step=10),
            OptimizationParamRange(name="n_drop", min=1, max=2, step=1),
        ],
        optimization_target="sharpe_ratio",
        max_parallel=2,
    )

    progress_updates = []

    async def _on_progress(meta):
        progress_updates.append(meta)

    result = await service.run_optimization(
        request,
        progress_callback=_on_progress,
        optimization_id="opt-1",
    )

    assert result.optimization_id == "opt-1"
    assert len(result.all_results) == 4
    assert all(call[2] == "optimization" for call in service.backtest_service.calls)
    assert len(progress_updates) == 4
    assert progress_updates[-1]["completed_count"] == 4
    assert progress_updates[-1]["progress"] == 1.0
    assert progress_updates[-1]["best_params"] == {"topk": 30, "n_drop": 2}
