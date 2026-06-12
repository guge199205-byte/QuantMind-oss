"""市场感知的数据状态扫描器。

供 API 实时调用（`/admin/models/data-status`）和 Celery 后台预热
（`engine.tasks.get_data_status_task`）共享，避免双方扫描逻辑漂移。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.shared.trading_calendar import calendar_service

from .model_management_utils import _scan_feature_snapshots_status


# 市场 → Qlib 子目录
_MARKET_QLIB_DIRS: dict[str, Path] = {
    "a_share": Path(os.getcwd()) / "db" / "qlib_data",
    "crypto": Path(os.getcwd()) / "db" / "qlib_data" / "crypto_data",
    "hong_kong": Path(os.getcwd()) / "db" / "qlib_data" / "hk_data",
    "us_stock": Path(os.getcwd()) / "db" / "qlib_data" / "us_data",
}

# 市场 → 交易日历服务 market 代码
_CALENDAR_MARKET_MAP: dict[str, str] = {
    "a_share": "SSE",
    "crypto": "SSE",  # 7x24，用 A 股日历近似
    "hong_kong": "HKEX",
    "us_stock": "NYSE",
}


def _resolve_qlib_dir(market: str) -> Path:
    return _MARKET_QLIB_DIRS.get(market, _MARKET_QLIB_DIRS["a_share"])


def _resolve_calendar_market(market: str) -> str:
    return _CALENDAR_MARKET_MAP.get(market, "SSE")


async def _resolve_trade_date(market: str, tenant_id: str, user_id: str) -> str:
    """根据市场日历返回当前应参照的交易日 ISO 字符串。"""
    now_local = datetime.now(ZoneInfo("Asia/Shanghai"))
    cal_market = _resolve_calendar_market(market)

    if now_local.time() < datetime.strptime("09:30", "%H:%M").time():
        trade_date_obj = await calendar_service.prev_trading_day(
            market=cal_market,
            trade_date=now_local.date(),
            tenant_id=tenant_id,
            user_id=user_id,
        )
    else:
        is_td = await calendar_service.is_trading_day(
            market=cal_market,
            trade_date=now_local.date(),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if is_td:
            trade_date_obj = now_local.date()
        else:
            trade_date_obj = await calendar_service.prev_trading_day(
                market=cal_market,
                trade_date=now_local.date(),
                tenant_id=tenant_id,
                user_id=user_id,
            )
    return trade_date_obj.isoformat()


def _scan_qlib_info(qlib_data_dir: Path, market: str) -> dict[str, Any]:
    """扫描指定市场的 Qlib 目录元数据。"""
    calendar_files: list[str] = []
    cal_dir = qlib_data_dir / "calendars"
    if cal_dir.exists():
        for f in cal_dir.iterdir():
            if f.suffix == ".txt":
                calendar_files.append(f.name)

    cal_file = (
        "5min.txt"
        if market == "crypto" and (cal_dir / "5min.txt").exists()
        else "day.txt"
    )
    calendars_path = qlib_data_dir / "calendars" / cal_file
    instruments_all_path = qlib_data_dir / "instruments" / "all.txt"
    features_root = qlib_data_dir / "features"

    qlib_info: dict[str, Any] = {
        "qlib_dir": str(qlib_data_dir),
        "exists": qlib_data_dir.exists() and qlib_data_dir.is_dir(),
        "calendar_total_days": 0,
        "calendar_start_date": None,
        "calendar_last_date": None,
        "calendar_files": calendar_files,
        "instruments": {"total": 0, "sh": 0, "sz": 0, "bj": 0, "other": 0},
        "feature_dirs_total": 0,
        "feature_dirs_sh_sz_bj": 0,
        "latest_date_coverage": {
            "target_date": None,
            "at_target_count": 0,
            "older_count": 0,
            "invalid_count": 0,
        },
    }

    if calendars_path.exists():
        try:
            calendar = [
                x.strip()
                for x in calendars_path.read_text(encoding="utf-8").splitlines()
                if x.strip()
            ]
            if calendar:
                qlib_info["calendar_total_days"] = len(calendar)
                qlib_info["calendar_start_date"] = calendar[0]
                qlib_info["calendar_last_date"] = calendar[-1]
                qlib_info["latest_date_coverage"]["target_date"] = calendar[-1]
        except Exception:
            pass

    if instruments_all_path.exists():
        try:
            for line in instruments_all_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                code = line.split()[0].strip().upper()
                qlib_info["instruments"]["total"] += 1
                if code.startswith("SH"):
                    qlib_info["instruments"]["sh"] += 1
                elif code.startswith("SZ"):
                    qlib_info["instruments"]["sz"] += 1
                elif code.startswith("BJ"):
                    qlib_info["instruments"]["bj"] += 1
                else:
                    qlib_info["instruments"]["other"] += 1
        except Exception:
            pass

    if features_root.exists() and features_root.is_dir():
        feature_dirs = [p for p in features_root.iterdir() if p.is_dir()]
        qlib_info["feature_dirs_total"] = len(feature_dirs)
        qlib_info["sync_partial"] = True

    return qlib_info


async def scan_data_status(
    market: str = "a_share",
    tenant_id: str = "default",
    user_id: str = "admin",
) -> dict[str, Any]:
    """市场感知的数据状态扫描。

    返回结构与原 `/admin/models/data-status` 响应保持一致，供 API 直接序列化、
    Celery worker 直接写入 Redis。
    """
    now_local = datetime.now(ZoneInfo("Asia/Shanghai"))
    trade_date = await _resolve_trade_date(market, tenant_id, user_id)

    qlib_data_dir = _resolve_qlib_dir(market)
    qlib_info = _scan_qlib_info(qlib_data_dir, market)
    feature_snapshots_info = _scan_feature_snapshots_status(
        target_date=trade_date,
        topn=20,
        market=market,
    )

    return {
        "checked_at": now_local.isoformat(),
        "trade_date": trade_date,
        "market": market,
        "qlib_data": qlib_info,
        "feature_snapshots": feature_snapshots_info,
    }
