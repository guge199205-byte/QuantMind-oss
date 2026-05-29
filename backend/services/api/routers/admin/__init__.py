from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .data_platform import router as data_platform_router
from .model_management import router as model_management_router
from .model_management_ops import router as model_management_ops_router
from .admin_training import router as admin_training_router
from .strategy_templates import router as strategy_templates_router
from .users import router as users_router
from .alpha_factor_pipeline import router as alpha_factor_pipeline_router
from .trading_agents import router as trading_agents_router
from .daily_analysis import router as daily_analysis_router
from .go_stock import router as go_stock_router

admin_router = APIRouter()
admin_router.include_router(
    dashboard_router, prefix="/dashboard", tags=["Admin-Dashboard"]
)
admin_router.include_router(
    admin_training_router, prefix="/models", tags=["Admin-ModelTraining"]
)
admin_router.include_router(
    model_management_router, prefix="/models", tags=["Admin-ModelManagement"]
)
admin_router.include_router(
    model_management_ops_router, prefix="/data", tags=["Admin-DataManagement"]
)
admin_router.include_router(
    users_router, prefix="/users", tags=["Admin-Users"]
)
admin_router.include_router(
    strategy_templates_router, prefix="/strategy-templates", tags=["Admin-StrategyTemplates"]
)
admin_router.include_router(
    data_platform_router, prefix="/data-platform", tags=["Admin-DataPlatform"]
)
admin_router.include_router(
    alpha_factor_pipeline_router, prefix="/alpha-factors", tags=["Admin-AlphaFactorPipeline"]
)
admin_router.include_router(
    trading_agents_router, prefix="/trading-agents", tags=["Admin-TradingAgents"]
)
admin_router.include_router(
    daily_analysis_router, prefix="/daily-analysis", tags=["Admin-DailyAnalysis"]
)
admin_router.include_router(
    go_stock_router, prefix="/go-stock", tags=["Admin-GoStock"]
)
