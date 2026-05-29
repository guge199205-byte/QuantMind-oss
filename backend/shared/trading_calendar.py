from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session

logger = logging.getLogger(__name__)

_DEFAULT_MARKET_TZ: dict[str, str] = {
    "SSE": "Asia/Shanghai",
    "SZSE": "Asia/Shanghai",
    "CFFEX": "Asia/Shanghai",
}

_DEFAULT_SESSIONS: dict[str, list[dict[str, Any]]] = {
    "SSE": [
        {"session_name": "AM", "start_time": "09:30:00", "end_time": "11:30:00", "cross_day": False},
        {"session_name": "PM", "start_time": "13:00:00", "end_time": "15:00:00", "cross_day": False},
    ],
    "SZSE": [
        {"session_name": "AM", "start_time": "09:30:00", "end_time": "11:30:00", "cross_day": False},
        {"session_name": "PM", "start_time": "13:00:00", "end_time": "15:00:00", "cross_day": False},
    ],
}

_MARKET_TO_XCAL = {
    "SSE": "XSHG",
    "SZSE": "XSHG",
    "CFFEX": "XSHG",
}


@dataclass
class SessionWindow:
    session_name: str
    start_at: datetime
    end_at: datetime
    cross_day: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_name": self.session_name,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "cross_day": self.cross_day,
        }


class TradingCalendarService:
    async def ensure_tables(self) -> None:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS qm_market_calendar_day (
                market VARCHAR(32) NOT NULL,
                trade_date DATE NOT NULL,
                is_trading_day BOOLEAN NOT NULL,
                timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
                source VARCHAR(64) NOT NULL DEFAULT 'manual',
                version VARCHAR(64),
                tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
                user_id VARCHAR(64) NOT NULL DEFAULT '*',
                metadata_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (market, trade_date, tenant_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS qm_market_trading_session (
                market VARCHAR(32) NOT NULL,
                session_name VARCHAR(64) NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                cross_day BOOLEAN NOT NULL DEFAULT FALSE,
                trade_date_rule VARCHAR(64) NOT NULL DEFAULT 'TRADE_DATE',
                timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
                tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
                user_id VARCHAR(64) NOT NULL DEFAULT '*',
                metadata_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (market, session_name, tenant_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS qm_market_calendar_exception (
                id BIGSERIAL PRIMARY KEY,
                market VARCHAR(32) NOT NULL,
                trade_date DATE NOT NULL,
                action VARCHAR(16) NOT NULL,
                reason TEXT,
                tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
                user_id VARCHAR(64) NOT NULL DEFAULT '*',
                approved_by VARCHAR(128),
                metadata_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS qm_market_calendar_version (
                market VARCHAR(32) NOT NULL,
                year INTEGER NOT NULL,
                checksum VARCHAR(128) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                source VARCHAR(64),
                published_at TIMESTAMPTZ,
                metadata_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (market, year)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_qm_calendar_day_query
            ON qm_market_calendar_day (market, tenant_id, user_id, trade_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_qm_calendar_exception_query
            ON qm_market_calendar_exception (market, tenant_id, user_id, trade_date)
            """,
        ]
        async with get_session() as session:
            for stmt in stmts:
                await session.execute(text(stmt))

    @staticmethod
    def _normalize_scope(tenant_id: str | None, user_id: str | None) -> tuple[str, str]:
        tenant = str(tenant_id or "default").strip() or "default"
        user = str(user_id or "").strip()
        if not user:
            raise ValueError("user_id is required")
        return tenant, user

    @staticmethod
    def _normalize_market(market: str) -> str:
        m = str(market or "").strip().upper()
        if not m:
            raise ValueError("market is required")
        return m

    @staticmethod
    def _normalize_trade_date(value: date | datetime | str) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        text_value = str(value).strip()
        if not text_value:
            raise ValueError("trade_date is required")
        return date.fromisoformat(text_value[:10])

    @staticmethod
    def _parse_time_value(v: Any) -> time:
        if isinstance(v, time):
            return v
        raw = str(v).strip()
        if len(raw) == 5:
            raw = f"{raw}:00"
        return time.fromisoformat(raw)

    @staticmethod
    def _safe_timezone(tz_name: str | None, market: str) -> str:
        candidate = str(tz_name or "").strip()
        if not candidate:
            candidate = _DEFAULT_MARKET_TZ.get(market, "Asia/Shanghai")
        try:
            ZoneInfo(candidate)
            return candidate
        except Exception:
            logger.warning("Invalid timezone %s for market %s, fallback Asia/Shanghai", candidate, market)
            return "Asia/Shanghai"

    async def upsert_calendar_day(
        self,
        *,
        market: str,
        trade_date: date | datetime | str,
        is_trading_day: bool,
        tenant_id: str,
        user_id: str,
        timezone_name: str | None = None,
        source: str = "manual",
        version: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        tenant, user = self._normalize_scope(tenant_id, user_id)
        mkt = self._normalize_market(market)
        d = self._normalize_trade_date(trade_date)
        tz = self._safe_timezone(timezone_name, mkt)
        payload = metadata_json or {}
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO qm_market_calendar_day (
                        market, trade_date, is_trading_day, timezone, source, version,
                        tenant_id, user_id, metadata_json, updated_at
                    ) VALUES (
                        :market, :trade_date, :is_trading_day, :timezone, :source, :version,
                        :tenant_id, :user_id, CAST(:metadata_json AS JSONB), NOW()
                    )
                    ON CONFLICT (market, trade_date, tenant_id, user_id)
                    DO UPDATE SET
                        is_trading_day = EXCLUDED.is_trading_day,
                        timezone = EXCLUDED.timezone,
                        source = EXCLUDED.source,
                        version = EXCLUDED.version,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = NOW()
                    """
                ),
                {
                    "market": mkt,
                    "trade_date": d,
                    "is_trading_day": bool(is_trading_day),
                    "timezone": tz,
                    "source": str(source or "manual"),
                    "version": version,
                    "tenant_id": tenant,
                    "user_id": user,
                    "metadata_json": json.dumps(payload, ensure_ascii=False),
                },
            )

    async def upsert_trading_sessions(
        self,
        *,
        market: str,
        sessions: list[dict[str, Any]],
        tenant_id: str,
        user_id: str,
        timezone_name: str | None = None,
    ) -> None:
        if not sessions:
            return
        tenant, user = self._normalize_scope(tenant_id, user_id)
        mkt = self._normalize_market(market)
        tz = self._safe_timezone(timezone_name, mkt)
        async with get_session() as session:
            for item in sessions:
                session_name = str(item.get("session_name") or "").strip().upper()
                if not session_name:
                    continue
                start_t = self._parse_time_value(item.get("start_time", "09:30:00"))
                end_t = self._parse_time_value(item.get("end_time", "15:00:00"))
                cross_day = bool(item.get("cross_day", False))
                rule = str(item.get("trade_date_rule") or "TRADE_DATE").strip().upper()
                meta = item.get("metadata_json") or {}
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_market_trading_session (
                            market, session_name, start_time, end_time, cross_day, trade_date_rule,
                            timezone, tenant_id, user_id, metadata_json, updated_at
                        ) VALUES (
                            :market, :session_name, :start_time, :end_time, :cross_day, :trade_date_rule,
                            :timezone, :tenant_id, :user_id, CAST(:metadata_json AS JSONB), NOW()
                        )
                        ON CONFLICT (market, session_name, tenant_id, user_id)
                        DO UPDATE SET
                            start_time = EXCLUDED.start_time,
                            end_time = EXCLUDED.end_time,
                            cross_day = EXCLUDED.cross_day,
                            trade_date_rule = EXCLUDED.trade_date_rule,
                            timezone = EXCLUDED.timezone,
                            metadata_json = EXCLUDED.metadata_json,
                            updated_at = NOW()
                        """
                    ),
                    {
                        "market": mkt,
                        "session_name": session_name,
                        "start_time": start_t,
                        "end_time": end_t,
                        "cross_day": cross_day,
                        "trade_date_rule": rule,
                        "timezone": tz,
                        "tenant_id": tenant,
                        "user_id": user,
                        "metadata_json": json.dumps(meta, ensure_ascii=False),
                    },
                )

    async def is_trading_day(
        self,
        *,
        market: str,
        trade_date: date | datetime | str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        mkt = self._normalize_market(market)
        d = self._normalize_trade_date(trade_date)
        record = await self._find_day_record(market=mkt, trade_date=d, tenant_id=tenant_id, user_id=user_id)
        if record is not None:
            return bool(record["is_trading_day"])
        return self._fallback_is_trading_day(mkt, d)

    async def next_trading_day(
        self,
        *,
        market: str,
        trade_date: date | datetime | str,
        tenant_id: str,
        user_id: str,
    ) -> date:
        mkt = self._normalize_market(market)
        cursor = self._normalize_trade_date(trade_date) + timedelta(days=1)
        for _ in range(370):
            if await self.is_trading_day(
                market=mkt,
                trade_date=cursor,
                tenant_id=tenant_id,
                user_id=user_id,
            ):
                return cursor
            cursor += timedelta(days=1)
        raise RuntimeError(f"next_trading_day not found in 370 days for market={mkt}")

    async def prev_trading_day(
        self,
        *,
        market: str,
        trade_date: date | datetime | str,
        tenant_id: str,
        user_id: str,
    ) -> date:
        mkt = self._normalize_market(market)
        cursor = self._normalize_trade_date(trade_date) - timedelta(days=1)
        for _ in range(370):
            if await self.is_trading_day(
                market=mkt,
                trade_date=cursor,
                tenant_id=tenant_id,
                user_id=user_id,
            ):
                return cursor
            cursor -= timedelta(days=1)
        raise RuntimeError(f"prev_trading_day not found in 370 days for market={mkt}")

    async def get_sessions(
        self,
        *,
        market: str,
        trade_date: date | datetime | str,
        tenant_id: str,
        user_id: str,
    ) -> list[SessionWindow]:
        mkt = self._normalize_market(market)
        d = self._normalize_trade_date(trade_date)
        rows = await self._find_sessions(market=mkt, tenant_id=tenant_id, user_id=user_id)
        if not rows:
            rows = _DEFAULT_SESSIONS.get(mkt, [])
        tz_name = self._safe_timezone(
            str(rows[0].get("timezone") or "") if rows else None,
            mkt,
        )
        tz = ZoneInfo(tz_name)
        windows: list[SessionWindow] = []
        for row in rows:
            s_name = str(row.get("session_name") or "").strip().upper()
            if not s_name:
                continue
            start_t = self._parse_time_value(row.get("start_time", "09:30:00"))
            end_t = self._parse_time_value(row.get("end_time", "15:00:00"))
            cross_day = bool(row.get("cross_day", False))
            start_at = datetime.combine(d, start_t, tzinfo=tz)
            end_at = datetime.combine(d, end_t, tzinfo=tz)
            if cross_day or end_at <= start_at:
                end_at += timedelta(days=1)
            windows.append(
                SessionWindow(
                    session_name=s_name,
                    start_at=start_at,
                    end_at=end_at,
                    cross_day=bool(cross_day),
                )
            )
        windows.sort(key=lambda x: x.start_at)
        return windows

    async def is_trading_time(
        self,
        *,
        market: str,
        dt: datetime | None,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        mkt = self._normalize_market(market)
        market_tz = ZoneInfo(_DEFAULT_MARKET_TZ.get(mkt, "Asia/Shanghai"))
        now_dt = dt or datetime.now(market_tz)
        local_dt = now_dt.astimezone(market_tz)
        local_date = local_dt.date()
        if not await self.is_trading_day(
            market=mkt,
            trade_date=local_date,
            tenant_id=tenant_id,
            user_id=user_id,
        ):
            return {
                "is_trading_time": False,
                "matched_session": None,
                "timezone": getattr(local_dt.tzinfo, "key", str(local_dt.tzinfo)),
            }
        sessions = await self.get_sessions(
            market=mkt,
            trade_date=local_date,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        for window in sessions:
            if window.start_at <= local_dt <= window.end_at:
                return {
                    "is_trading_time": True,
                    "matched_session": window.session_name,
                    "timezone": getattr(local_dt.tzinfo, "key", str(local_dt.tzinfo)),
                }
        return {
            "is_trading_time": False,
            "matched_session": None,
            "timezone": getattr(local_dt.tzinfo, "key", str(local_dt.tzinfo)),
        }

    async def batch_is_trading_day(
        self,
        *,
        market: str,
        dates: list[date | datetime | str],
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in dates:
            d = self._normalize_trade_date(raw)
            is_td = await self.is_trading_day(
                market=market,
                trade_date=d,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            result.append({"date": d.isoformat(), "is_trading_day": is_td})
        return result

    async def _find_day_record(
        self,
        *,
        market: str,
        trade_date: date,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        tenant, user = self._normalize_scope(tenant_id, user_id)
        scope = [
            (tenant, user, 1),
            (tenant, "*", 2),
            ("default", "*", 3),
        ]
        async with get_session(read_only=True) as session:
            try:
                row = await session.execute(
                    text(
                        """
                        SELECT is_trading_day, timezone, source, version
                        FROM qm_market_calendar_day
                        WHERE market = :market
                          AND trade_date = :trade_date
                          AND (
                            (tenant_id = :tenant_1 AND user_id = :user_1)
                            OR (tenant_id = :tenant_2 AND user_id = :user_2)
                            OR (tenant_id = :tenant_3 AND user_id = :user_3)
                          )
                        ORDER BY CASE
                            WHEN tenant_id = :tenant_1 AND user_id = :user_1 THEN 1
                            WHEN tenant_id = :tenant_2 AND user_id = :user_2 THEN 2
                            ELSE 3
                        END
                        LIMIT 1
                        """
                    ),
                    {
                        "market": market,
                        "trade_date": trade_date,
                        "tenant_1": scope[0][0],
                        "user_1": scope[0][1],
                        "tenant_2": scope[1][0],
                        "user_2": scope[1][1],
                        "tenant_3": scope[2][0],
                        "user_3": scope[2][1],
                    },
                )
                item = row.mappings().first()
                return dict(item) if item else None
            except Exception as exc:
                logger.warning("query qm_market_calendar_day failed, fallback enabled: %s", exc)
                return None

    async def _find_sessions(
        self,
        *,
        market: str,
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        tenant, user = self._normalize_scope(tenant_id, user_id)
        async with get_session(read_only=True) as session:
            try:
                rows = await session.execute(
                    text(
                        """
                        WITH ranked AS (
                            SELECT
                                session_name,
                                start_time,
                                end_time,
                                cross_day,
                                trade_date_rule,
                                timezone,
                                tenant_id,
                                user_id,
                                CASE
                                    WHEN tenant_id = :tenant_1 AND user_id = :user_1 THEN 1
                                    WHEN tenant_id = :tenant_2 AND user_id = :user_2 THEN 2
                                    WHEN tenant_id = :tenant_3 AND user_id = :user_3 THEN 3
                                    ELSE 99
                                END AS rank_no
                            FROM qm_market_trading_session
                            WHERE market = :market
                              AND (
                                (tenant_id = :tenant_1 AND user_id = :user_1)
                                OR (tenant_id = :tenant_2 AND user_id = :user_2)
                                OR (tenant_id = :tenant_3 AND user_id = :user_3)
                              )
                        ),
                        best_scope AS (
                            SELECT MIN(rank_no) AS best_rank
                            FROM ranked
                        )
                        SELECT
                            session_name,
                            start_time,
                            end_time,
                            cross_day,
                            trade_date_rule,
                            timezone,
                            tenant_id,
                            user_id
                        FROM ranked
                        WHERE rank_no = (SELECT best_rank FROM best_scope)
                        ORDER BY session_name ASC
                        """
                    ),
                    {
                        "market": market,
                        "tenant_1": tenant,
                        "user_1": user,
                        "tenant_2": tenant,
                        "user_2": "*",
                        "tenant_3": "default",
                        "user_3": "*",
                    },
                )
                return [dict(r) for r in rows.mappings().all()]
            except Exception as exc:
                logger.warning("query qm_market_trading_session failed, fallback enabled: %s", exc)
                return []

    def _fallback_is_trading_day(self, market: str, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        calendar_name = _MARKET_TO_XCAL.get(market)
        if not calendar_name:
            return True
        try:
            import exchange_calendars as xcals

            cal = xcals.get_calendar(calendar_name)
            return bool(cal.is_session(d))
        except Exception:
            logger.warning("exchange_calendars fallback failed for market=%s date=%s", market, d)
            return True


calendar_service = TradingCalendarService()
