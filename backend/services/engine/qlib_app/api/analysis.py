"""
高级分析API端点

提供基于Qlib的高级分析功能：
- 基础风险指标
- 绩效分析
- 交易统计
- 基准对比
- 持仓分析
- 因子分析
- 风格归因
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.services.engine.qlib_app.schemas.analysis import (
    BasicRiskRequest,
    BasicRiskResponse,
    BenchmarkComparisonRequest,
    BenchmarkComparisonResponse,
    FactorAnalysisRequest,
    FactorAnalysisResponse,
    PerformanceRequest,
    PerformanceResponse,
    PositionAnalysisRequest,
    PositionAnalysisResponse,
    StratifiedGroupReturn,
    StyleAttributionRequest,
    StyleAttributionResponse,
    StyleFactorExposure,
    TradeStatsRequest,
    TradeStatsResponse,
)
from backend.services.engine.qlib_app.services.basic_risk_service import (
    BasicRiskService,
)
from backend.services.engine.qlib_app.services.benchmark_service import BenchmarkService
from backend.services.engine.qlib_app.services.factor_analysis_service import (
    FactorAnalysisService,
)
from backend.services.engine.qlib_app.services.performance_service import (
    PerformanceService,
)
from backend.services.engine.qlib_app.services.position_service import (
    BacktestPositionService as PositionService,
)
from backend.services.engine.qlib_app.services.style_attribution_service import (
    StyleAttributionService,
)
from backend.services.engine.qlib_app.services.trade_stats_service import (
    TradeStatsService,
)
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# 服务实例
basic_risk_service = BasicRiskService()
performance_service = PerformanceService()
trade_stats_service = TradeStatsService()
benchmark_service = BenchmarkService()
position_service = PositionService()
factor_analysis_service = FactorAnalysisService()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """健康检查"""
    return {
        "status": "healthy",
        "service": "advanced_analysis",
        "version": "1.0.0",
    }


@router.post("/basic-risk", response_model=BasicRiskResponse)
async def analyze_basic_risk(request: BasicRiskRequest) -> BasicRiskResponse:
    """
    基础风险指标分析

    基于Qlib risk_analysis()计算核心风险指标：
    - 年化收益率、年化波动率
    - 夏普比率、最大回撤
    - Calmar比率、Sortino比率
    - 收益率分布和回撤曲线
    """
    try:
        task_log = StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "basic-risk", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        )
        task_log.info("request", "基础风险分析")

        result = await basic_risk_service.analyze(
            backtest_id=request.backtest_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )

        task_log.info("complete", "分析完成", sharpe=f"{result.metrics.sharpe_ratio:.2f}")
        return result

    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "basic-risk", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "basic-risk", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).exception("failed", "分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/performance", response_model=PerformanceResponse)
async def analyze_performance(
    request: PerformanceRequest,
) -> PerformanceResponse:
    """
    绩效分析

    提供多维度绩效评估：
    - 时间维度分析（月度、季度、年度）
    - 滚动指标（30日窗口）
    - 收益率分布分析
    """
    try:
        task_log = StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "performance", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        )
        task_log.info("request", "绩效分析")

        result = await performance_service.analyze(
            backtest_id=request.backtest_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            rolling_window=request.rolling_window or 30,
        )

        task_log.info("complete", "分析完成", yearly_return=f"{result.yearly_return:.2%}")
        return result

    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "performance", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "performance", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).exception("failed", "分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/trade-stats", response_model=TradeStatsResponse)
async def analyze_trade_stats(
    request: TradeStatsRequest,
) -> TradeStatsResponse:
    """交易统计分析"""
    try:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "trade-stats", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).info("request", "交易统计分析")
        result = await trade_stats_service.analyze(
            backtest_id=request.backtest_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )
        return result
    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "trade-stats", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "trade-stats", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).exception("failed", "分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/benchmark", response_model=BenchmarkComparisonResponse)
async def analyze_benchmark(
    request: BenchmarkComparisonRequest,
) -> BenchmarkComparisonResponse:
    """基准对比分析"""
    try:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "benchmark",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark_id": request.benchmark_id,
            },
        ).info("request", "基准对比分析")
        result = await benchmark_service.analyze(
            backtest_id=request.backtest_id,
            user_id=request.user_id,
            benchmark_id=request.benchmark_id,
            tenant_id=request.tenant_id,
        )
        return result
    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "benchmark",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark_id": request.benchmark_id,
            },
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "benchmark",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark_id": request.benchmark_id,
            },
        ).exception("failed", "分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/position", response_model=PositionAnalysisResponse)
async def analyze_position(
    request: PositionAnalysisRequest,
) -> PositionAnalysisResponse:
    """持仓分析"""
    try:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "position", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).info("request", "持仓分析")
        result = await position_service.analyze(
            backtest_id=request.backtest_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )
        return result
    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "position", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "position", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).exception("failed", "分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/factor-analysis", response_model=FactorAnalysisResponse)
async def analyze_factors(
    request: FactorAnalysisRequest,
) -> FactorAnalysisResponse:
    """
    因子/信号质量分析

    从已完成的回测结果中提取因子质量指标：
    - Rank IC / ICIR（预测分与实际收益的相关性）
    - 分层收益（按预测分分组的多空收益）

    若回测结果中已缓存因子指标，直接返回；否则基于可用数据重新计算。
    """
    try:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "factor-analysis", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).info("request", "因子分析")

        from backend.services.engine.qlib_app.services.backtest_persistence import (
            BacktestPersistence,
        )

        persistence = BacktestPersistence()
        result = await persistence.get_result(
            request.backtest_id,
            tenant_id=request.tenant_id,
            include_fields=["factor_metrics", "stratified_returns", "backtest_id"]
        )

        if not result:
            raise ValueError(f"回测结果不存在: {request.backtest_id}")

        factor_metrics = result.factor_metrics or {}
        stratified_raw = result.stratified_returns or []

        stratified = [
            StratifiedGroupReturn(
                group=int(g.get("group", i + 1)),
                avg_return=float(g.get("avg_return", 0.0)),
                total_return=float(g.get("total_return", 0.0)),
                volatility=float(g.get("volatility", 0.0)),
            )
            for i, g in enumerate(stratified_raw)
        ]

        data_available = bool(factor_metrics or stratified)

        return FactorAnalysisResponse(
            rank_ic=factor_metrics.get("rank_ic"),
            rank_ic_std=factor_metrics.get("rank_ic_std"),
            icir=factor_metrics.get("icir"),
            stratified_returns=stratified,
            data_available=data_available,
        )

    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "factor-analysis", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {"endpoint": "factor-analysis", "backtest_id": request.backtest_id, "tenant_id": request.tenant_id},
        ).exception("failed", "因子分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"因子分析失败: {str(e)}")


@router.post("/style-attribution", response_model=StyleAttributionResponse)
async def analyze_style_attribution(
    request: StyleAttributionRequest,
) -> StyleAttributionResponse:
    """
    风格归因分析

    分析组合在核心风格因子上的暴露度，并与基准对比：
    - 规模（Size）、价值（Value）、动量（Momentum）、波动率（Volatility）

    若回测结果中已缓存风格归因，直接返回；否则基于持仓数据重新计算。
    """
    try:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "style-attribution",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark": request.benchmark,
            },
        ).info("request", "风格归因分析")

        from backend.services.engine.qlib_app.services.backtest_persistence import (
            BacktestPersistence,
        )

        persistence = BacktestPersistence()
        result = await persistence.get_result(
            request.backtest_id,
            tenant_id=request.tenant_id,
            include_fields=["style_attribution", "positions", "config", "backtest_id"]
        )

        if not result:
            raise ValueError(f"回测结果不存在: {request.backtest_id}")

        # 优先使用已缓存的风格归因结果
        cached = result.style_attribution
        if cached and isinstance(cached, dict) and cached.get("portfolio"):
            portfolio_exp = cached.get("portfolio", {})
            benchmark_exp = cached.get("benchmark", {})
            active_exp = cached.get("active", {})
            analysis_date = cached.get("date")

            factors = [
                StyleFactorExposure(
                    factor=factor,
                    portfolio=float(portfolio_exp.get(factor, 0.0)),
                    benchmark=float(benchmark_exp.get(factor, 0.0)),
                    active=float(active_exp.get(factor, 0.0)),
                )
                for factor in portfolio_exp
            ]

            return StyleAttributionResponse(
                factors=factors,
                analysis_date=str(analysis_date) if analysis_date else None,
                data_available=True,
            )

        # 若无缓存，尝试从持仓数据重新计算
        positions = result.positions or []
        if not positions:
            return StyleAttributionResponse(factors=[], data_available=False)

        config = result.config or {}
        start_date = config.get("start_date", "")
        end_date = config.get("end_date", "")

        attribution = await StyleAttributionService.analyze_portfolio_exposure(
            positions=positions,
            benchmark=request.benchmark,
            start_date=start_date,
            end_date=end_date,
        )

        if not attribution:
            return StyleAttributionResponse(factors=[], data_available=False)

        portfolio_exp = attribution.get("portfolio", {})
        benchmark_exp = attribution.get("benchmark", {})
        active_exp = attribution.get("active", {})

        factors = [
            StyleFactorExposure(
                factor=factor,
                portfolio=float(portfolio_exp.get(factor, 0.0)),
                benchmark=float(benchmark_exp.get(factor, 0.0)),
                active=float(active_exp.get(factor, 0.0)),
            )
            for factor in portfolio_exp
        ]

        return StyleAttributionResponse(
            factors=factors,
            analysis_date=attribution.get("date"),
            data_available=bool(factors),
        )

    except ValueError as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "style-attribution",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark": request.benchmark,
            },
        ).error("invalid_request", "参数错误", error=e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "analysis-api",
            {
                "endpoint": "style-attribution",
                "backtest_id": request.backtest_id,
                "tenant_id": request.tenant_id,
                "benchmark": request.benchmark,
            },
        ).exception("failed", "风格归因分析失败", error=e)
        raise HTTPException(status_code=500, detail=f"风格归因分析失败: {str(e)}")
