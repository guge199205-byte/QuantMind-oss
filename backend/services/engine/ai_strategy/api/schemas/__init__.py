"""AI 策略向导 - API Schema 定义"""

from .stock_pool import (
    NumericCondition,
    TrendCondition,
    CompositeCondition,
    Condition,
    ParseRequest,
    ParseResponse,
    QueryPoolRequest,
    PoolItem,
    QueryPoolResponse,
    SavePoolFileRequest,
    SavePoolFileResponse,
    DeletePoolFileRequest,
    DeletePoolFileResponse,
    ListPoolFilesRequest,
    PoolFileSummary,
    ListPoolFilesResponse,
    PreviewPoolFileRequest,
    PreviewPoolFileResponse,
    GetActivePoolFileRequest,
    GetActivePoolFileResponse,
)
from .strategy_params import (
    BuyRule,
    SellRule,
    RiskConfig,
    PositionConfig,
    ValidatePositionRequest,
    ValidatePositionResponse,
)
from .style import ApplyStyleRequest, ApplyStyleResponse
from .generation import (
    GenerateRequest,
    GenerateResponse,
    GenerateQlibRequest,
    GenerateQlibResponse,
    GenerateQlibTaskSubmitResponse,
    GenerateQlibTaskStatusResponse,
    SaveToCloudRequest,
    SaveToCloudResponse,
    ValidateQlibRequest,
    ValidationCheckResponse,
    ValidateQlibResponse,
    RepairQlibRequest,
    RepairQlibResponse,
)
from .backtest import BacktestRequest, BacktestResponse
from .text_parse import (
    ParseTextRequest,
    ParseTradeRulesRequest,
    TradeRule,
    ParseTradeRulesResponse,
)
from .market import MarketStateResponse
from .remote import ScanRemoteRequest, ImportRemoteRequest
