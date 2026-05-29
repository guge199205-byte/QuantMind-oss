"""
TradingCalendar 抽象 + 多市场实现。

数据来源（按优先级）：
1. PostgreSQL trading_calendar 表（由 cron 每日同步）
2. 内置静态文件 (后续补充 holidays_a.yaml / holidays_hk.yaml / holidays_us.yaml)
3. 默认按 ISO 工作日（周一-周五），仅作降级方案

接口：
    is_trading_day(d) -> bool
    next_trading_day(d) -> date
    prev_trading_day(d) -> date
    trading_days(start, end) -> list[date]
    is_half_day(d) -> bool
    market_open / market_close (datetime, 含时区)
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class TradingCalendar(ABC):
    market: str = ""
    tz: ZoneInfo = ZoneInfo("UTC")
    regular_open: time = time(9, 30)
    regular_close: time = time(15, 0)

    def __init__(self) -> None:
        self._cache: dict[date, tuple[bool, bool]] = {}
        self._cache_lock = threading.RLock()

    @abstractmethod
    def _lookup(self, d: date) -> tuple[bool, bool]:
        """返回 (is_trading_day, is_half_day)。子类决定数据来源。"""

    def is_trading_day(self, d: date) -> bool:
        return self._cached(d)[0]

    def is_half_day(self, d: date) -> bool:
        return self._cached(d)[1]

    def next_trading_day(self, d: date) -> date:
        cur = d + timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(cur):
                return cur
            cur += timedelta(days=1)
        raise RuntimeError(f"no trading day within 30 days after {d}")

    def prev_trading_day(self, d: date) -> date:
        cur = d - timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(cur):
                return cur
            cur -= timedelta(days=1)
        raise RuntimeError(f"no trading day within 30 days before {d}")

    def trading_days(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        cur = start
        while cur <= end:
            if self.is_trading_day(cur):
                out.append(cur)
            cur += timedelta(days=1)
        return out

    def market_open(self, d: date) -> datetime:
        return datetime.combine(d, self.regular_open, tzinfo=self.tz)

    def market_close(self, d: date) -> datetime:
        close_t = time(11, 30) if self.is_half_day(d) else self.regular_close
        return datetime.combine(d, close_t, tzinfo=self.tz)

    def _cached(self, d: date) -> tuple[bool, bool]:
        with self._cache_lock:
            if d in self._cache:
                return self._cache[d]
            v = self._lookup(d)
            self._cache[d] = v
            return v


class WeekdayFallbackCalendar(TradingCalendar):
    def _lookup(self, d: date) -> tuple[bool, bool]:
        return (d.weekday() < 5, False)


class _DbBackedCalendar(TradingCalendar):
    """DB 优先 + 周末降级。子类只需配置 market/tz/时段。"""

    def __init__(self, db_loader: Optional[Callable[[str, date], Optional[dict]]] = None) -> None:
        super().__init__()
        self._db_loader = db_loader

    def _lookup(self, d: date) -> tuple[bool, bool]:
        if self._db_loader:
            try:
                row = self._db_loader(self.market, d)
                if row is not None:
                    return (bool(row.get("is_trading")), bool(row.get("is_half_day", False)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s DB lookup failed: %s", self.__class__.__name__, exc)
        return (d.weekday() < 5, False)


class ChinaACalendar(_DbBackedCalendar):
    market = "A"
    tz = ZoneInfo("Asia/Shanghai")
    regular_open = time(9, 30)
    regular_close = time(15, 0)


class HongKongCalendar(_DbBackedCalendar):
    market = "HK"
    tz = ZoneInfo("Asia/Hong_Kong")
    regular_open = time(9, 30)
    regular_close = time(16, 0)


class UnitedStatesCalendar(_DbBackedCalendar):
    market = "US"
    tz = ZoneInfo("America/New_York")
    regular_open = time(9, 30)
    regular_close = time(16, 0)


_CALENDARS: dict[str, TradingCalendar] = {}
_CAL_LOCK = threading.Lock()


def get_calendar(
    market: str,
    *,
    db_loader: Optional[Callable[[str, date], Optional[dict]]] = None,
) -> TradingCalendar:
    m = (market or "").upper()
    with _CAL_LOCK:
        if m in _CALENDARS:
            return _CALENDARS[m]
        if m == "A":
            cal: TradingCalendar = ChinaACalendar(db_loader=db_loader)
        elif m == "HK":
            cal = HongKongCalendar(db_loader=db_loader)
        elif m == "US":
            cal = UnitedStatesCalendar(db_loader=db_loader)
        else:
            cal = WeekdayFallbackCalendar()
            cal.market = m
        _CALENDARS[m] = cal
        return cal


def reset_calendars() -> None:
    with _CAL_LOCK:
        _CALENDARS.clear()
