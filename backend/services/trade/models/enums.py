from enum import Enum


class _CaseInsensitiveEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        upper = text.upper()
        if upper in cls.__members__:
            return cls.__members__[upper]

        lower = text.lower()
        for member in cls:
            if str(member.value).lower() == lower:
                return member
        return None

class Exchange(str, Enum):
    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"
    SHFE = "SHFE"
    DCE = "DCE"
    CZCE = "CZCE"
    CFFEX = "CFFEX"
    INE = "INE"

class OrderSide(_CaseInsensitiveEnum):
    BUY = "buy"
    SELL = "sell"


class PositionSide(_CaseInsensitiveEnum):
    LONG = "long"
    SHORT = "short"


class TradeAction(_CaseInsensitiveEnum):
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_CLOSE = "sell_to_close"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"

class OrderType(_CaseInsensitiveEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"

class OrderStatus(_CaseInsensitiveEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    OPEN = "submitted"
    PARTIAL = "partially_filled"

class TradingMode(_CaseInsensitiveEnum):
    SIMULATION = "SIMULATION"
    REAL = "REAL"
    SHADOW = "SHADOW"
    BACKTEST = "SIMULATION"
