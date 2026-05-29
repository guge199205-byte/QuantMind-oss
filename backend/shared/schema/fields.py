# 统一字段常量与映射
# 若需扩展，请同步更新 docs/data_dictionary.md

# 基础通用字段
SYMBOL = "symbol"
EXCHANGE = "exchange"
NAME = "name"
DATETIME = "datetime"
DATE = "date"

# 行情/快照字段
PRICE = "price"
CHANGE_PCT = "change_pct"
CHANGE = "change"
VOLUME = "volume"
AMOUNT = "amount"
HIGH = "high"
LOW = "low"
OPEN = "open"
PRE_CLOSE = "pre_close"
VOLUME_RATIO = "volume_ratio"
TURNOVER_RATE = "turnover_rate"
PE_RATIO = "pe_ratio"
PB_RATIO = "pb_ratio"
MARKET_CAP = "market_cap"
CIRCULATING_MARKET_CAP = "circulating_market_cap"
SPEED = "speed"
CHANGE_5M = "change_5m"
CHANGE_60D = "change_60d"
CHANGE_YTD = "change_ytd"
INDUSTRY = "industry"
ADJUST_TYPE = "adjust_type"

# 中文 -> 英文映射（用于脚本标准化）
CHINESE_TO_STD = {
    "代码": SYMBOL,
    "名称": NAME,
    "最新价": PRICE,
    "涨跌幅": CHANGE_PCT,
    "涨跌额": CHANGE,
    "成交量": VOLUME,
    "成交额": AMOUNT,
    "振幅": "amplitude",
    "最高": HIGH,
    "最低": LOW,
    "今开": OPEN,
    "昨收": PRE_CLOSE,
    "量比": VOLUME_RATIO,
    "换手率": TURNOVER_RATE,
    "市盈率_动态": PE_RATIO,
    "市净率": PB_RATIO,
    "总市值": MARKET_CAP,
    "流通市值": CIRCULATING_MARKET_CAP,
    "涨速": SPEED,
    "五分钟涨跌": CHANGE_5M,
    "六十日涨跌幅": CHANGE_60D,
    "年初至今涨跌幅": CHANGE_YTD,
}

# 允许缺失（不影响主流程）的可选字段
OPTIONAL_FIELDS = {VOLUME_RATIO, SPEED, CHANGE_5M, CHANGE_60D, CHANGE_YTD}

# ==================== 用户相关字段 ====================
USER_ID = "user_id"
USERNAME = "username"
EMAIL = "email"
PHONE = "phone"
PASSWORD = "password"
ROLE = "role"
STATUS = "status"
CREATED_AT = "created_at"
UPDATED_AT = "updated_at"
LAST_LOGIN = "last_login"
AVATAR = "avatar"
PREFERENCES = "preferences"

# ==================== 策略相关字段 ====================
STRATEGY_ID = "strategy_id"
STRATEGY_NAME = "strategy_name"
STRATEGY_TYPE = "strategy_type"
STRATEGY_CODE = "strategy_code"
STRATEGY_DESC = "strategy_description"
PARAMETERS = "parameters"
INDICATORS = "indicators"
TIMEFRAME = "timeframe"
ASSET_CLASS = "asset_class"

# ==================== 回测相关字段 ====================
BACKTEST_ID = "backtest_id"
START_DATE = "start_date"
END_DATE = "end_date"
INITIAL_CAPITAL = "initial_capital"
FINAL_CAPITAL = "final_capital"
TOTAL_RETURN = "total_return"
ANNUAL_RETURN = "annual_return"
SHARPE_RATIO = "sharpe_ratio"
MAX_DRAWDOWN = "max_drawdown"
WIN_RATE = "win_rate"
PROFIT_FACTOR = "profit_factor"
TOTAL_TRADES = "total_trades"

# ==================== 交易相关字段 ====================
ORDER_ID = "order_id"
TRADE_ID = "trade_id"
ORDER_TYPE = "order_type"
ORDER_SIDE = "order_side"
ORDER_STATUS = "order_status"
QUANTITY = "quantity"
FILLED_QTY = "filled_qty"
FILLED_PRICE = "filled_price"
COMMISSION = "commission"
SLIPPAGE = "slippage"
POSITION = "position"
POSITION_SIZE = "position_size"

# ==================== 风险管理字段 ====================
RISK_LEVEL = "risk_level"
MAX_POSITION_SIZE = "max_position_size"
STOP_LOSS = "stop_loss"
TAKE_PROFIT = "take_profit"
VAR = "value_at_risk"
BETA = "beta"
ALPHA = "alpha"
VOLATILITY = "volatility"

# ==================== 市场数据扩展字段 ====================
BID = "bid"
ASK = "ask"
BID_SIZE = "bid_size"
ASK_SIZE = "ask_size"
OPEN_INTEREST = "open_interest"
SETTLEMENT_PRICE = "settlement_price"
PREV_SETTLEMENT = "prev_settlement"

# ==================== 技术指标字段 ====================
MA5 = "ma5"
MA10 = "ma10"
MA20 = "ma20"
MA60 = "ma60"
EMA12 = "ema12"
EMA26 = "ema26"
MACD = "macd"
MACD_SIGNAL = "macd_signal"
MACD_HIST = "macd_histogram"
RSI = "rsi"
KDJ_K = "kdj_k"
KDJ_D = "kdj_d"
KDJ_J = "kdj_j"
BOLL_UPPER = "boll_upper"
BOLL_MIDDLE = "boll_middle"
BOLL_LOWER = "boll_lower"

# ==================== 中文映射扩展 ====================
CHINESE_TO_STD.update(
    {
        # 用户相关
        "用户ID": USER_ID,
        "用户名": USERNAME,
        "邮箱": EMAIL,
        "手机": PHONE,
        "密码": PASSWORD,
        "角色": ROLE,
        "状态": STATUS,
        "创建时间": CREATED_AT,
        "更新时间": UPDATED_AT,
        "最后登录": LAST_LOGIN,
        "头像": AVATAR,
        "偏好设置": PREFERENCES,
        # 策略相关
        "策略ID": STRATEGY_ID,
        "策略名称": STRATEGY_NAME,
        "策略类型": STRATEGY_TYPE,
        "策略代码": STRATEGY_CODE,
        "策略描述": STRATEGY_DESC,
        "参数": PARAMETERS,
        "指标": INDICATORS,
        "时间周期": TIMEFRAME,
        "资产类别": ASSET_CLASS,
        # 回测相关
        "回测ID": BACKTEST_ID,
        "开始日期": START_DATE,
        "结束日期": END_DATE,
        "初始资金": INITIAL_CAPITAL,
        "最终资金": FINAL_CAPITAL,
        "总收益": TOTAL_RETURN,
        "年化收益": ANNUAL_RETURN,
        "夏普比率": SHARPE_RATIO,
        "最大回撤": MAX_DRAWDOWN,
        "胜率": WIN_RATE,
        "盈利因子": PROFIT_FACTOR,
        "总交易次数": TOTAL_TRADES,
        # 交易相关
        "订单ID": ORDER_ID,
        "交易ID": TRADE_ID,
        "订单类型": ORDER_TYPE,
        "买卖方向": ORDER_SIDE,
        "订单状态": ORDER_STATUS,
        "数量": QUANTITY,
        "成交数量": FILLED_QTY,
        "成交价格": FILLED_PRICE,
        "手续费": COMMISSION,
        "滑点": SLIPPAGE,
        "持仓": POSITION,
        "持仓大小": POSITION_SIZE,
        # 风险管理
        "风险等级": RISK_LEVEL,
        "最大持仓": MAX_POSITION_SIZE,
        "止损": STOP_LOSS,
        "止盈": TAKE_PROFIT,
        "风险价值": VAR,
        "贝塔": BETA,
        "阿尔法": ALPHA,
        "波动率": VOLATILITY,
        # 市场数据扩展
        "买价": BID,
        "卖价": ASK,
        "买量": BID_SIZE,
        "卖量": ASK_SIZE,
        "持仓量": OPEN_INTEREST,
        "结算价": SETTLEMENT_PRICE,
        "昨结算": PREV_SETTLEMENT,
        # 技术指标
        "5日均线": MA5,
        "10日均线": MA10,
        "20日均线": MA20,
        "60日均线": MA60,
        "12日指数均线": EMA12,
        "26日指数均线": EMA26,
        "MACD": MACD,
        "MACD信号": MACD_SIGNAL,
        "MACD柱": MACD_HIST,
        "相对强弱指数": RSI,
        "KDJ_K": KDJ_K,
        "KDJ_D": KDJ_D,
        "KDJ_J": KDJ_J,
        "布林上轨": BOLL_UPPER,
        "布林中轨": BOLL_MIDDLE,
        "布林下轨": BOLL_LOWER,
    }
)

__all__ = [
    # 基础通用字段
    "SYMBOL",
    "EXCHANGE",
    "NAME",
    "DATETIME",
    "DATE",
    # 行情/快照字段
    "PRICE",
    "CHANGE_PCT",
    "CHANGE",
    "VOLUME",
    "AMOUNT",
    "HIGH",
    "LOW",
    "OPEN",
    "PRE_CLOSE",
    "VOLUME_RATIO",
    "TURNOVER_RATE",
    "PE_RATIO",
    "PB_RATIO",
    "MARKET_CAP",
    "CIRCULATING_MARKET_CAP",
    "SPEED",
    "CHANGE_5M",
    "CHANGE_60D",
    "CHANGE_YTD",
    "INDUSTRY",
    "ADJUST_TYPE",
    # 用户相关字段
    "USER_ID",
    "USERNAME",
    "EMAIL",
    "PHONE",
    "PASSWORD",
    "ROLE",
    "STATUS",
    "CREATED_AT",
    "UPDATED_AT",
    "LAST_LOGIN",
    "AVATAR",
    "PREFERENCES",
    # 策略相关字段
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_TYPE",
    "STRATEGY_CODE",
    "STRATEGY_DESC",
    "PARAMETERS",
    "INDICATORS",
    "TIMEFRAME",
    "ASSET_CLASS",
    # 回测相关字段
    "BACKTEST_ID",
    "START_DATE",
    "END_DATE",
    "INITIAL_CAPITAL",
    "FINAL_CAPITAL",
    "TOTAL_RETURN",
    "ANNUAL_RETURN",
    "SHARPE_RATIO",
    "MAX_DRAWDOWN",
    "WIN_RATE",
    "PROFIT_FACTOR",
    "TOTAL_TRADES",
    # 交易相关字段
    "ORDER_ID",
    "TRADE_ID",
    "ORDER_TYPE",
    "ORDER_SIDE",
    "ORDER_STATUS",
    "QUANTITY",
    "FILLED_QTY",
    "FILLED_PRICE",
    "COMMISSION",
    "SLIPPAGE",
    "POSITION",
    "POSITION_SIZE",
    # 风险管理字段
    "RISK_LEVEL",
    "MAX_POSITION_SIZE",
    "STOP_LOSS",
    "TAKE_PROFIT",
    "VAR",
    "BETA",
    "ALPHA",
    "VOLATILITY",
    # 市场数据扩展字段
    "BID",
    "ASK",
    "BID_SIZE",
    "ASK_SIZE",
    "OPEN_INTEREST",
    "SETTLEMENT_PRICE",
    "PREV_SETTLEMENT",
    # 技术指标字段
    "MA5",
    "MA10",
    "MA20",
    "MA60",
    "EMA12",
    "EMA26",
    "MACD",
    "MACD_SIGNAL",
    "MACD_HIST",
    "RSI",
    "KDJ_K",
    "KDJ_D",
    "KDJ_J",
    "BOLL_UPPER",
    "BOLL_MIDDLE",
    "BOLL_LOWER",
    # 映射和配置
    "CHINESE_TO_STD",
    "OPTIONAL_FIELDS",
]
