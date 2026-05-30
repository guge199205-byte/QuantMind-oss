#!/usr/bin/env python3
"""
统一日常数据同步脚本
====================

数据源优先级（A 股日线）：
  1. investment_data (qlib_bin) — 最准，T-2 左右
  2. baostock — 稳定，T-1
  3. akshare (stock_zh_a_daily) — T-1，新浪源
  4. eltdx — T（当天），通达信

流程：
  1. 查 PG: 每只股票的 MAX(trade_date)
  2. PG 最新 < investment_data 最新 → 从 qlib_bin 读增量写入 PG
  3. PG 最新 < 今天 → baostock 补齐 → akshare 兜底
  4. 需要当日 → eltdx 获取
  5. 增量数据追加写入本地 qlib bin
  6. 计算 MA/收益率等技术指标

用法：
  # 增量同步（默认，只补缺失天数）
  python backend/scripts/daily_data_sync.py --market A --incremental

  # 全量同步（重写所有数据）
  python backend/scripts/daily_data_sync.py --market A --full

  # 指定股票
  python backend/scripts/daily_data_sync.py --incremental --symbols 600519.SH,000001.SZ

  # 仅更新 investment_data（下载最新 qlib_bin）
  python backend/scripts/daily_data_sync.py --update-investment-data

  # 仅校准指标
  python backend/scripts/daily_data_sync.py --calibrate-only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import struct
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily_sync")

# ---------------------------------------------------------------------------
# Paths & DB config
# ---------------------------------------------------------------------------
QLIB_DATA_DIR = PROJECT_ROOT / "db" / "qlib_data"
INVESTMENT_DATA_DIR = Path(
    os.getenv("QM_INVESTMENT_DATA_DIR", "/data/third_party/investment_data")
)

DB_HOST = os.getenv("DB_HOST", os.getenv("DB_MASTER_HOST", "127.0.0.1"))
DB_PORT = int(os.getenv("DB_PORT", os.getenv("DB_MASTER_PORT", "5432")))
DB_NAME = os.getenv("DB_NAME", "quantmind")
DB_USER = os.getenv("DB_USER", "quantmind")
DB_PASS = os.getenv("DB_PASSWORD", "quantmind")


def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        url = url.replace("asyncpg", "psycopg2")
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url
    from urllib.parse import quote_plus as _q
    return f"postgresql+psycopg2://{DB_USER}:{_q(DB_PASS)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# ---------------------------------------------------------------------------
# Sync progress tracking (Redis)
# ---------------------------------------------------------------------------
_SYNC_PROGRESS_KEY = "quantmind:sync:progress"

_SYNC_STEPS = [
    ("init", "初始化"),
    ("pg_query", "查询PG最新数据"),
    ("data_sync", "多源数据同步"),
    ("qlib_bin", "更新Qlib二进制"),
    ("calibrate", "校准技术指标"),
    ("parquet", "更新特征Parquet"),
    ("done", "完成"),
]


def _update_sync_progress(step: str, detail: str = "", pct: int = 0, current: int = 0, total: int = 0):
    """Write current sync step to Redis for frontend polling."""
    try:
        import redis as _redis
        rds = _redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), socket_timeout=1)
        data = {
            "step": step,
            "detail": detail,
            "pct": pct,
            "current": current,
            "total": total,
            "updated_at": datetime.now().isoformat(),
        }
        rds.set(_SYNC_PROGRESS_KEY, json.dumps(data), ex=1800)  # 30min TTL
    except Exception:
        pass


def get_sync_progress() -> dict:
    """Read current sync progress from Redis."""
    try:
        import redis as _redis
        rds = _redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), socket_timeout=1)
        raw = rds.get(_SYNC_PROGRESS_KEY)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {"step": "idle", "detail": "", "pct": 0, "current": 0, "total": 0}


def clear_sync_progress():
    """Clear sync progress from Redis."""
    try:
        import redis as _redis
        rds = _redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), socket_timeout=1)
        rds.delete(_SYNC_PROGRESS_KEY)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Qlib bin helpers
# ---------------------------------------------------------------------------
_QLIB_ROOT_CACHE: Optional[Path] = None
_CALENDAR_CACHE: Optional[np.ndarray] = None


def _find_qlib_root() -> Optional[Path]:
    """Find qlib_bin root, preferring the one with the most recent calendar."""
    candidates = []
    for root in (QLIB_DATA_DIR, INVESTMENT_DATA_DIR):
        for cand in (root / "qlib_bin", root):
            cal = cand / "calendars" / "day.txt"
            if cal.exists() and (cand / "features").exists():
                try:
                    last_line = cal.read_text().strip().splitlines()[-1].strip()
                    candidates.append((last_line, cand))
                except Exception:
                    candidates.append(("", cand))
    if not candidates:
        return None
    # Pick the one with the most recent calendar date
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _qlib_root() -> Path:
    """Get qlib root, cached. Raises if not found."""
    global _QLIB_ROOT_CACHE
    if _QLIB_ROOT_CACHE is not None:
        return _QLIB_ROOT_CACHE
    root = _find_qlib_root()
    if root is None:
        raise RuntimeError("Qlib data directory not found")
    _QLIB_ROOT_CACHE = root
    return root


def _load_calendar() -> np.ndarray:
    global _CALENDAR_CACHE
    if _CALENDAR_CACHE is not None:
        return _CALENDAR_CACHE
    qroot = _qlib_root()
    cal_path = qroot / "calendars" / "day.txt"
    lines = cal_path.read_text().strip().splitlines()
    _CALENDAR_CACHE = np.array([l.strip() for l in lines if l.strip()], dtype="datetime64[D]")
    return _CALENDAR_CACHE


def _read_qlib_bin(path: Path) -> tuple[int, np.ndarray]:
    raw = path.read_bytes()
    if len(raw) < 4:
        raise ValueError(f"{path} too small")
    start_idx = int(struct.unpack("<f", raw[:4])[0])
    n = (len(raw) - 4) // 4
    values = np.frombuffer(raw, dtype=np.float32, count=n, offset=4).copy()
    return start_idx, values


def _qlib_symbol(symbol: str) -> str:
    """600519.SH -> sh600519"""
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}{code}"
    return s.lower()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _get_engine():
    from sqlalchemy import create_engine
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif "asyncpg" in db_url:
        db_url = db_url.replace("asyncpg", "psycopg2")
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)


def _get_pg_latest_dates(engine) -> dict[str, date]:
    """返回 {symbol: max_trade_date} 字典。"""
    from sqlalchemy import text as sql_text
    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("SELECT symbol, MAX(trade_date) AS max_dt FROM stock_daily_latest GROUP BY symbol")
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def _get_pg_symbol_list(engine) -> list[str]:
    """从 stock_daily_latest 获取所有 symbol。"""
    from sqlalchemy import text as sql_text
    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("SELECT DISTINCT symbol FROM stock_daily_latest ORDER BY symbol")
        ).fetchall()
    return [r[0] for r in rows]


def _get_all_qlib_symbols() -> list[str]:
    """从 qlib_bin instruments/all.txt 获取所有 symbol。"""
    qroot = _qlib_root()
    inst_path = qroot / "instruments" / "all.txt"
    if not inst_path.exists():
        return []
    symbols = set()
    for line in inst_path.read_text().splitlines():
        parts = line.strip().split("\t")
        if parts and parts[0]:
            # sh600519 -> 600519.SH
            sym = parts[0].strip().lower()
            if len(sym) >= 2 and sym[:2] in ("sh", "sz", "bj"):
                code = sym[2:]
                ex = sym[:2].upper()
                symbols.add(f"{code}.{ex}")
            else:
                symbols.add(sym.upper())
    return sorted(symbols)


# ---------------------------------------------------------------------------
# Data source: investment_data (qlib_bin)
# ---------------------------------------------------------------------------
def _read_investment_data(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """从 qlib_bin 读取指定 symbol 的日线数据。"""
    qroot = _qlib_root()
    qsym = _qlib_symbol(symbol)
    sym_dir = qroot / "features" / qsym
    if not sym_dir.exists():
        return None

    calendar = _load_calendar()
    cal_len = len(calendar)

    field_map = {
        "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume", "amount": "amount",
        "factor": "adj_factor",
    }
    series: dict[str, np.ndarray] = {}
    for qf, std in field_map.items():
        f = sym_dir / f"{qf}.day.bin"
        if not f.exists():
            continue
        try:
            start_idx, vals = _read_qlib_bin(f)
        except Exception:
            continue
        full = np.full(cal_len, np.nan, dtype=np.float64)
        end_idx = min(start_idx + len(vals), cal_len)
        full[start_idx:end_idx] = vals[:end_idx - start_idx]
        series[std] = full

    if "close" not in series:
        return None

    df = pd.DataFrame(series)
    df["trade_date"] = pd.to_datetime(calendar).date
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    if df.empty:
        return None

    if start:
        df = df[df["trade_date"] >= start]
    if end:
        df = df[df["trade_date"] <= end]
    if df.empty:
        return None

    df["symbol"] = symbol.upper()
    for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor"):
        if c not in df.columns:
            df[c] = pd.NA
    df["adj_factor"] = df["adj_factor"].fillna(1.0)
    df["source"] = "investment_data"
    return df[["symbol", "trade_date", "open", "high", "low", "close",
               "volume", "amount", "adj_factor", "source"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Data source: baostock
# ---------------------------------------------------------------------------
_BS_LOGGED_IN = False


def _ensure_baostock():
    global _BS_LOGGED_IN
    if _BS_LOGGED_IN:
        return
    import baostock as bs
    rs = bs.login()
    if rs.error_code != "0":
        raise RuntimeError(f"baostock login failed: {rs.error_msg}")
    _BS_LOGGED_IN = True


def _to_bs_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}.{code}"
    return s.lower()


def _read_baostock(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    try:
        import baostock as bs
        _ensure_baostock()
    except Exception:
        return None
    try:
        rs = bs.query_history_k_data_plus(
            _to_bs_symbol(symbol),
            "date,open,high,low,close,volume,amount,adjustflag,turn,pctChg",
            start_date=start.isoformat() if start else "",
            end_date=end.isoformat() if end else "",
            frequency="d",
            adjustflag="2",  # 前复权
        )
        if rs.error_code != "0":
            return None
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        for c in ("open", "high", "low", "close", "volume", "amount", "turn", "pctChg"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["adj_factor"] = 1.0
        df["source"] = "baostock"
        return df[["symbol", "trade_date", "open", "high", "low", "close",
                    "volume", "amount", "adj_factor", "source"]]
    except Exception as exc:
        log.debug("baostock failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Data source: akshare
# ---------------------------------------------------------------------------
def _read_akshare(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
    except ImportError:
        return None
    try:
        # 尝试 stock_zh_a_hist (东方财富源)
        code = symbol.strip().upper().split(".")[0]
        raw = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d") if start else "20000101",
            end_date=end.strftime("%Y%m%d") if end else "20991231",
            adjust="qfq",
        )
        if raw is not None and not raw.empty:
            rename = {
                "日期": "trade_date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
            }
            df = raw.rename(columns=rename).copy()
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            df["symbol"] = symbol.upper()
            for c in ("open", "high", "low", "close", "volume", "amount"):
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df["adj_factor"] = 1.0
            df["source"] = "akshare"
            return df[["symbol", "trade_date", "open", "high", "low", "close",
                        "volume", "amount", "adj_factor", "source"]]
    except Exception:
        pass

    # 备用: stock_zh_a_daily (新浪源)
    try:
        s = symbol.strip().upper()
        if "." in s:
            code, ex = s.split(".", 1)
            prefix = f"{ex.lower()}{code}"
        else:
            prefix = s.lower()
        raw = ak.stock_zh_a_daily(symbol=prefix, adjust="qfq")
        if raw is not None and not raw.empty:
            rename = {
                "date": "trade_date", "open": "open", "close": "close",
                "high": "high", "low": "low", "volume": "volume", "amount": "amount",
            }
            df = raw.rename(columns=rename).copy()
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            if start:
                df = df[df["trade_date"] >= start]
            if end:
                df = df[df["trade_date"] <= end]
            if df.empty:
                return None
            df["symbol"] = symbol.upper()
            for c in ("open", "high", "low", "close", "volume", "amount"):
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df["adj_factor"] = 1.0
            df["source"] = "akshare"
            return df[["symbol", "trade_date", "open", "high", "low", "close",
                        "volume", "amount", "adj_factor", "source"]]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Data source: eltdx (today's data)
# ---------------------------------------------------------------------------
def _read_eltdx(symbol: str) -> Optional[pd.DataFrame]:
    try:
        from mootdx.quotes import Quotes
    except ImportError:
        return None
    try:
        client = Quotes.factory(market="std")
        code = symbol.strip().upper().split(".")[0]
        raw = client.bars(symbol=code, frequency=9, offset=10)
        if raw is None or len(raw) == 0:
            return None
        df = raw.copy()
        if "datetime" in df.columns:
            df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
        elif "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        else:
            df["trade_date"] = pd.to_datetime(df.index).date
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = pd.NA
        df["adj_factor"] = 1.0
        df["source"] = "eltdx"
        return df[["symbol", "trade_date", "open", "high", "low", "close",
                    "volume", "amount", "adj_factor", "source"]]
    except Exception as exc:
        log.debug("eltdx failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# PostgreSQL upsert
# ---------------------------------------------------------------------------
def _upsert_to_pg(engine, df: pd.DataFrame) -> int:
    """将 DataFrame 写入 stock_daily_latest（UPSERT）。"""
    from sqlalchemy import text as sql_text

    if df is None or df.empty:
        return 0

    df = df.copy()
    df = df.drop_duplicates(subset=["trade_date", "symbol"])

    # 只保留 OHLCV 核心列
    core_cols = ["trade_date", "symbol", "open", "high", "low", "close",
                 "volume", "amount", "adj_factor"]
    use_cols = [c for c in core_cols if c in df.columns]
    data = df[use_cols].fillna(0)
    data = data.replace([float("inf"), float("-inf")], 0)

    records = [tuple(row) for row in data.itertuples(index=False, name=None)]
    if not records:
        return 0

    non_pk = [c for c in use_cols if c not in ("trade_date", "symbol")]

    with engine.begin() as conn:
        for rec in records:
            rec_dict = dict(zip(use_cols, rec))
            placeholders = ", ".join([f":{c}" for c in use_cols])
            cols = ", ".join(use_cols)
            if non_pk:
                update_set = ", ".join([f"{c}=EXCLUDED.{c}" for c in non_pk])
                sql = (
                    f"INSERT INTO stock_daily_latest ({cols}) VALUES ({placeholders}) "
                    f"ON CONFLICT (trade_date, symbol) DO UPDATE SET {update_set}"
                )
            else:
                sql = (
                    f"INSERT INTO stock_daily_latest ({cols}) VALUES ({placeholders}) "
                    "ON CONFLICT (trade_date, symbol) DO NOTHING"
                )
            conn.execute(sql_text(sql), rec_dict)

    return len(records)


# ---------------------------------------------------------------------------
# Qlib bin incremental update
# ---------------------------------------------------------------------------
def _sync_qlib_calendar() -> int:
    """将 investment_data 的 calendar 同步到 QLIB_DATA_DIR，返回新增天数。"""
    qroot = _find_qlib_root()
    if qroot is None:
        return 0
    src = qroot / "calendars" / "day.txt"
    dst = QLIB_DATA_DIR / "calendars" / "day.txt"
    if not src.exists():
        return 0
    src_lines = src.read_text().strip().splitlines()
    if dst.exists():
        dst_lines = dst.read_text().strip().splitlines()
    else:
        dst_lines = []
    if src_lines == dst_lines:
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(src_lines) + "\n")
    added = len(src_lines) - len(dst_lines)
    log.info("Qlib calendar synced: %d → %d (+%d days)", len(dst_lines), len(src_lines), added)
    return added


def _update_qlib_bin(df: pd.DataFrame) -> int:
    """将新数据追加到本地 qlib bin 文件。

    使用 investment_data 的 calendar 作为索引参考，写入 QLIB_DATA_DIR。
    自动同步 calendar 文件确保日期对齐。
    """
    # 先同步 calendar，确保新日期可用
    _sync_qlib_calendar()

    qroot = _find_qlib_root()
    if qroot is None:
        log.debug("No qlib root found, skipping bin update")
        return 0

    calendar = _load_calendar()
    cal_len = len(calendar)

    # 检查数据中是否有日历里没有的新交易日，自动扩展日历
    global _CALENDAR_CACHE
    new_dates_in_data = sorted(set(
        np.datetime64(d) for d in df["trade_date"].unique()
        if np.datetime64(d) not in calendar
    ))
    if new_dates_in_data:
        cal_path = QLIB_DATA_DIR / "calendars" / "day.txt"
        existing_lines = cal_path.read_text().strip().splitlines() if cal_path.exists() else []
        added = 0
        for nd in new_dates_in_data:
            ds = str(nd)[:10]  # YYYY-MM-DD
            if ds not in existing_lines:
                existing_lines.append(ds)
                added += 1
        if added:
            existing_lines.sort()
            cal_path.write_text("\n".join(existing_lines) + "\n")
            calendar = np.array(existing_lines, dtype="datetime64")
            cal_len = len(calendar)
            _CALENDAR_CACHE = calendar
            log.info("Calendar extended with %d new trading days, now %d days", added, cal_len)
    updated = 0

    for sym, group in df.groupby("symbol"):
        qsym = _qlib_symbol(sym)
        sym_dir = QLIB_DATA_DIR / "features" / qsym
        sym_dir.mkdir(parents=True, exist_ok=True)

        group = group.sort_values("trade_date")

        for field_col, qlib_field in [("open", "open"), ("high", "high"),
                                       ("low", "low"), ("close", "close"),
                                       ("volume", "volume"), ("amount", "amount"),
                                       ("adj_factor", "factor")]:
            if field_col not in group.columns:
                continue

            bin_path = sym_dir / f"{qlib_field}.day.bin"

            if bin_path.exists():
                # 读取现有数据并扩展
                try:
                    start_idx, existing = _read_qlib_bin(bin_path)
                except Exception:
                    continue

                for _, row in group.iterrows():
                    td = np.datetime64(row["trade_date"])
                    cal_idx = int(np.searchsorted(calendar, td))
                    if cal_idx >= cal_len or calendar[cal_idx] != td:
                        continue
                    # 扩展数组 if needed
                    if cal_idx < start_idx or cal_idx >= start_idx + len(existing):
                        new_start = min(start_idx, cal_idx)
                        new_end = max(start_idx + len(existing), cal_idx + 1)
                        new_arr = np.full(new_end - new_start, np.nan, dtype=np.float32)
                        new_arr[start_idx - new_start:start_idx - new_start + len(existing)] = existing
                        existing = new_arr
                        start_idx = new_start
                    val = row[field_col]
                    if pd.notna(val):
                        existing[cal_idx - start_idx] = float(val)

                header = struct.pack("<f", float(start_idx))
                bin_path.write_bytes(header + existing.tobytes())
            else:
                # 新建：定位第一笔数据在 calendar 中的位置
                first_td = np.datetime64(group["trade_date"].iloc[0])
                first_idx = int(np.searchsorted(calendar, first_td))
                if first_idx >= cal_len:
                    continue
                arr = np.full(len(group), np.nan, dtype=np.float32)
                for i, (_, row) in enumerate(group.iterrows()):
                    val = row[field_col]
                    if pd.notna(val):
                        arr[i] = float(val)
                header = struct.pack("<f", float(first_idx))
                bin_path.write_bytes(header + arr.tobytes())

        updated += 1

    return updated


# ---------------------------------------------------------------------------
# Technical indicators calibration
# ---------------------------------------------------------------------------
def _calibrate_indicators(engine, symbols: Optional[list[str]] = None, days: int = 90):
    """计算 MA/收益率/换手率等技术指标并更新 stock_daily_latest。"""
    from sqlalchemy import text as sql_text

    log.info("Calibrating technical indicators (last %d days)...", days)
    cutoff = date.today() - timedelta(days=days)

    with engine.begin() as conn:
        if symbols:
            # 指定股票
            sym_filter = "AND symbol = ANY(:symbols)"
            params = {"cutoff": cutoff, "symbols": symbols}
        else:
            sym_filter = ""
            params = {"cutoff": cutoff}

        # 读取原始数据
        rows = conn.execute(
            sql_text(f"""
                SELECT symbol, trade_date, open, high, low, close, volume, amount, adj_factor
                FROM stock_daily_latest
                WHERE trade_date >= :cutoff {sym_filter}
                ORDER BY symbol, trade_date
            """),
            params,
        ).fetchall()

    if not rows:
        log.info("No data to calibrate")
        return

    df = pd.DataFrame(rows, columns=["symbol", "trade_date", "open", "high", "low",
                                      "close", "volume", "amount", "adj_factor"])
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    log.info("Calibrating %d rows for %d symbols...", len(df), df["symbol"].nunique())

    # 计算指标
    df = df.sort_values(["symbol", "trade_date"])

    # MA
    for p in (5, 10, 20, 60):
        df[f"ma{p}"] = df.groupby("symbol")["close"].transform(
            lambda x: x.rolling(p, min_periods=1).mean()
        )
        df[f"ma_gap_{p}"] = ((df["close"] / df[f"ma{p}"]) - 1) * 100

    # 收益率
    df["ret"] = df.groupby("symbol")["close"].pct_change()
    df["return_1d"] = df.groupby("symbol")["close"].pct_change(1)
    df["return_3d"] = df.groupby("symbol")["close"].pct_change(3)
    df["return_5d"] = df.groupby("symbol")["close"].pct_change(5)
    df["return_10d"] = df.groupby("symbol")["close"].pct_change(10)
    df["return_20d"] = df.groupby("symbol")["close"].pct_change(20)
    df["return_60d"] = df.groupby("symbol")["close"].pct_change(60)

    # 波动率
    df["vol_std_5"] = df.groupby("symbol")["ret"].transform(
        lambda x: x.rolling(5, min_periods=1).std() * 100
    )
    df["vol_std_20"] = df.groupby("symbol")["ret"].transform(
        lambda x: x.rolling(20, min_periods=1).std() * 100
    )
    df["vol_std_60"] = df.groupby("symbol")["ret"].transform(
        lambda x: x.rolling(60, min_periods=1).std() * 100
    )

    # 涨跌幅
    df["pct_change"] = df["ret"] * 100

    # 写回数据库
    update_cols = [
        "ma5", "ma10", "ma20", "ma60",
        "ma_gap_5", "ma_gap_10", "ma_gap_20",
        "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "return_60d",
        "vol_std_5", "vol_std_20", "vol_std_60",
        "pct_change",
    ]

    # 批量更新
    batch_size = 500
    total_updated = 0
    with engine.begin() as conn:
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size]
            for _, row in batch.iterrows():
                sets = []
                params = {"sym": row["symbol"], "td": row["trade_date"]}
                for col in update_cols:
                    val = row.get(col)
                    if pd.notna(val) and not (isinstance(val, float) and (np.isinf(val) or np.isnan(val))):
                        sets.append(f"{col} = :{col}")
                        params[col] = float(val)
                if sets:
                    conn.execute(
                        sql_text(
                            f"UPDATE stock_daily_latest SET {', '.join(sets)} "
                            "WHERE symbol = :sym AND trade_date = :td"
                        ),
                        params,
                    )
                    total_updated += 1

    log.info("Indicators calibrated: %d rows updated", total_updated)


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------
def run_sync(
    market: str = "A",
    symbols: Optional[list[str]] = None,
    incremental: bool = True,
    update_qlib: bool = True,
    calibrate: bool = True,
    calibrate_days: int = 90,
) -> dict:
    """执行统一数据同步。"""
    result = {
        "market": market,
        "mode": "incremental" if incremental else "full",
        "started": datetime.now().isoformat(),
        "investment_data_synced": 0,
        "baostock_synced": 0,
        "akshare_synced": 0,
        "eltdx_synced": 0,
        "qlib_bin_updated": 0,
        "indicators_calibrated": False,
        "errors": [],
    }

    engine = _get_engine()
    _update_sync_progress("init", "初始化同步环境...", pct=5)

    # 1. 确定股票列表
    if symbols:
        target_symbols = symbols
    else:
        # 合并 PG 已有 + qlib instruments
        pg_symbols = set(_get_pg_symbol_list(engine))
        qlib_symbols = set(_get_all_qlib_symbols())
        target_symbols = sorted(pg_symbols | qlib_symbols)
        log.info("Target symbols: %d (PG: %d, Qlib: %d)",
                 len(target_symbols), len(pg_symbols), len(qlib_symbols))

    if not target_symbols:
        log.warning("No symbols to sync")
        return result

    # 2. 获取 PG 最新日期
    pg_latest = _get_pg_latest_dates(engine)
    log.info("PG has %d symbols, latest dates loaded", len(pg_latest))

    # 3. 确定投资数据最新日期
    inv_latest_date: Optional[date] = None
    qroot = _find_qlib_root()
    if qroot:
        cal = _load_calendar()
        if len(cal) > 0:
            inv_latest_date = pd.to_datetime(cal[-1]).date()
            log.info("Investment data calendar: %s to %s (%d days)",
                     cal[0], cal[-1], len(cal))

    today = date.today()

    # 4. 同步每只股票
    _update_sync_progress("pg_query", "查询PG最新日期...", pct=10)
    inv_count = 0
    bs_count = 0
    ak_count = 0
    eltdx_count = 0
    all_new_data = []

    total = len(target_symbols)
    # 快速跳过已到 T-1 的股票，避免白跑循环
    yesterday = today - timedelta(days=1)
    skip_count = 0
    need_sync_symbols = []
    for sym in target_symbols:
        pg_max = pg_latest.get(sym)
        if incremental and pg_max is not None and pg_max >= yesterday:
            skip_count += 1
            continue
        need_sync_symbols.append(sym)
    log.info("Skip %d already-up-to-date symbols, syncing %d", skip_count, len(need_sync_symbols))

    # --- Phase 1: 批量读取 investment_data（本地文件，快） ---
    inv_batch: list[pd.DataFrame] = []
    still_need_symbols: list[str] = []
    if inv_latest_date and need_sync_symbols:
        _update_sync_progress("data_sync", f"Phase 1: 批量读取 investment_data ({len(need_sync_symbols)} 只)...", pct=12, current=0, total=len(need_sync_symbols))
        for idx, sym in enumerate(need_sync_symbols):
            if (idx + 1) % 1000 == 0:
                log.info("investment_data batch: %d/%d", idx + 1, len(need_sync_symbols))
                pct = 12 + int(18 * (idx + 1) / len(need_sync_symbols))
                _update_sync_progress("data_sync", f"investment_data {idx+1}/{len(need_sync_symbols)}", pct=pct, current=idx+1, total=len(need_sync_symbols))
            pg_max = pg_latest.get(sym)
            partition_start = date(2026, 1, 1)
            need_start = None
            if pg_max is None:
                need_start = partition_start
            elif pg_max < inv_latest_date:
                need_start = max(pg_max + timedelta(days=1), partition_start)
            if need_start and need_start <= inv_latest_date:
                try:
                    inv_df = _read_investment_data(sym, need_start, inv_latest_date)
                    if inv_df is not None and not inv_df.empty:
                        inv_batch.append(inv_df)
                        inv_count += 1
                        # 检查是否还需要baostock补
                        max_inv = inv_df["trade_date"].max()
                        if isinstance(max_inv, date):
                            pass
                        else:
                            max_inv = date.fromisoformat(str(max_inv))
                        if max_inv < today:
                            still_need_symbols.append(sym)
                        continue
                except Exception as exc:
                    log.debug("investment_data failed for %s: %s", sym, exc)
            # 没有investment_data数据，直接进baostock列表
            still_need_symbols.append(sym)
        if inv_batch:
            inv_combined = pd.concat(inv_batch, ignore_index=True)
            rows = _upsert_to_pg(engine, inv_combined)
            all_new_data.append(inv_combined)
            log.info("Phase 1 done: investment_data %d symbols, %d rows", inv_count, len(inv_combined))
    else:
        still_need_symbols = list(need_sync_symbols)

    # --- Phase 2: baostock/akshare 补剩余缺口 ---
    _update_sync_progress("data_sync", f"Phase 2: baostock 补缺 {len(still_need_symbols)} 只...", pct=35, current=0, total=len(still_need_symbols))
    for idx, sym in enumerate(still_need_symbols):
        if (idx + 1) % 500 == 0:
            log.info("baostock: %d/%d symbols", idx + 1, len(still_need_symbols))
            pct = 35 + int(35 * (idx + 1) / len(still_need_symbols))
            _update_sync_progress("data_sync", f"baostock {idx+1}/{len(still_need_symbols)}", pct=pct, current=idx+1, total=len(still_need_symbols))

        pg_max = pg_latest.get(sym)
        need_start: Optional[date] = None
        partition_start = date(2026, 1, 1)

        if incremental:
            if pg_max is None:
                need_start = partition_start
            elif pg_max < today:
                need_start = max(pg_max + timedelta(days=1), partition_start)
            else:
                continue
        else:
            need_start = partition_start

        if need_start is None:
            continue

        # --- Source 2: baostock (fill gap to T-1) ---
        bs_end = today - timedelta(days=1)
        bs_start = need_start

        new_df = None
        if bs_start <= bs_end:
            bs_df = _read_baostock(sym, bs_start, bs_end)
            if bs_df is not None and not bs_df.empty:
                new_df = bs_df
                bs_count += 1

        # --- Source 3: akshare (fallback) ---
        ak_start = bs_start
        if new_df is not None and not new_df.empty:
            max_dt = new_df["trade_date"].max()
            if isinstance(max_dt, date):
                ak_start = max_dt + timedelta(days=1)
            else:
                ak_start = date.fromisoformat(str(max_dt)) + timedelta(days=1)

        if ak_start <= bs_end and (new_df is None or new_df.empty):
            ak_df = _read_akshare(sym, ak_start, bs_end)
            if ak_df is not None and not ak_df.empty:
                if new_df is not None and not new_df.empty:
                    new_df = pd.concat([new_df, ak_df], ignore_index=True)
                else:
                    new_df = ak_df
                ak_count += 1

        # --- Source 4: eltdx (today) ---
        if today.weekday() < 5:  # 工作日
            eltdx_needed = False
            if new_df is None or new_df.empty:
                eltdx_needed = True
            else:
                max_dt = new_df["trade_date"].max()
                if isinstance(max_dt, date):
                    eltdx_needed = max_dt < today
                else:
                    eltdx_needed = date.fromisoformat(str(max_dt)) < today

            if eltdx_needed:
                eltdx_df = _read_eltdx(sym)
                if eltdx_df is not None and not eltdx_df.empty:
                    # 只取今天的
                    eltdx_today = eltdx_df[eltdx_df["trade_date"] == today]
                    if not eltdx_today.empty:
                        if new_df is not None and not new_df.empty:
                            new_df = pd.concat([new_df, eltdx_today], ignore_index=True)
                        else:
                            new_df = eltdx_today
                        eltdx_count += 1

        # --- 写入 PG ---
        if new_df is not None and not new_df.empty:
            new_df = new_df.drop_duplicates(subset=["trade_date", "symbol"])
            try:
                rows = _upsert_to_pg(engine, new_df)
                all_new_data.append(new_df)
            except Exception as exc:
                result["errors"].append(f"{sym}: {exc}")
                log.debug("PG upsert failed for %s: %s", sym, exc)

    result["investment_data_synced"] = inv_count
    result["baostock_synced"] = bs_count
    result["akshare_synced"] = ak_count
    result["eltdx_synced"] = eltdx_count

    log.info("Sync complete: inv=%d, baostock=%d, akshare=%d, eltdx=%d",
             inv_count, bs_count, ak_count, eltdx_count)

    # 5. 更新 qlib bin
    if update_qlib and all_new_data:
        _update_sync_progress("qlib_bin", "更新Qlib二进制文件...", pct=75)
        combined = pd.concat(all_new_data, ignore_index=True)
        try:
            qlib_updated = _update_qlib_bin(combined)
            result["qlib_bin_updated"] = qlib_updated
            log.info("Qlib bin updated: %d symbols", qlib_updated)
        except Exception as exc:
            result["errors"].append(f"qlib_bin: {exc}")
            log.warning("Qlib bin update failed: %s", exc)

    # 6. 校准指标
    if calibrate:
        _update_sync_progress("calibrate", "校准技术指标...", pct=85)
        try:
            _calibrate_indicators(engine, symbols=symbols, days=calibrate_days)
            result["indicators_calibrated"] = True
        except Exception as exc:
            result["errors"].append(f"calibrate: {exc}")
            log.warning("Indicator calibration failed: %s", exc)

    # 7. 增量更新 feature parquet
    _update_sync_progress("parquet", "更新特征Parquet...", pct=92)
    try:
        parquet_result = update_feature_parquet()
        result["parquet_updated"] = parquet_result
        log.info("Feature parquet updated: %s", parquet_result.get("status", "ok"))
    except Exception as exc:
        result["errors"].append(f"parquet: {exc}")
        log.warning("Feature parquet update failed: %s", exc)

    # 关闭 baostock
    if _BS_LOGGED_IN:
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass

    result["finished"] = datetime.now().isoformat()
    _update_sync_progress("done", "同步完成!", pct=100)
    return result


# ---------------------------------------------------------------------------
# Update investment_data from GitHub
# ---------------------------------------------------------------------------
def update_investment_data(version: str = "") -> dict:
    """下载最新 investment_data qlib_bin 并解压。"""
    log.info("Updating investment_data...")
    # 复用 sync_investment_data.py 的逻辑
    from backend.scripts.sync_investment_data import (
        _get_latest_version, _download_asset, _extract_qlib_data,
        DOWNLOAD_DIR, ASSET_NAME,
    )

    if not version:
        version = _get_latest_version()
    log.info("Target version: %s", version)

    archive_path = DOWNLOAD_DIR / version / ASSET_NAME
    if not archive_path.exists():
        _download_asset(version, archive_path)
    else:
        log.info("Archive already exists: %s", archive_path)

    _extract_qlib_data(archive_path)

    # 清除缓存，确保后续读取使用最新数据
    global _QLIB_ROOT_CACHE, _CALENDAR_CACHE
    _QLIB_ROOT_CACHE = None
    _CALENDAR_CACHE = None

    return {"version": version, "status": "ok"}


# ---------------------------------------------------------------------------
# Feature parquet incremental update
# ---------------------------------------------------------------------------
def update_feature_parquet(since: str = "", until: str = "") -> dict:
    """增量更新 feature parquet（从 stock_daily_latest 补充缺失日期）。"""
    log.info("Updating feature parquet...")
    try:
        from backend.scripts.update_feature_parquet import (
            PARQUET_PATH, fetch_data, compute_all_features,
        )
    except ImportError as e:
        return {"status": "skipped", "reason": f"import failed: {e}"}

    if not PARQUET_PATH.exists():
        return {"status": "skipped", "reason": "parquet file not found"}

    import asyncio as _asyncio

    existing = pd.read_parquet(PARQUET_PATH, engine="pyarrow")
    existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date
    max_date = existing["trade_date"].max()

    since_date = date.fromisoformat(since) if since else max_date + timedelta(days=1)
    until_date = date.fromisoformat(until) if until else date.today()

    if since_date > until_date:
        log.info("Feature parquet already up to date (max=%s)", max_date)
        return {"status": "up_to_date", "max_date": str(max_date)}

    log.info("Feature parquet: updating %s to %s (existing max=%s)", since_date, until_date, max_date)

    db_df = _asyncio.run(fetch_data(since_date, until_date, lookback_days=120))
    if db_df.empty:
        return {"status": "skipped", "reason": "no new data in DB"}

    target_dates = set()
    d = since_date
    while d <= until_date:
        target_dates.add(d)
        d += timedelta(days=1)

    new_data = compute_all_features(db_df, target_dates)
    if new_data.empty:
        return {"status": "skipped", "reason": "no valid features computed"}

    # 合并：去掉重叠日期，追加新数据
    overlap = set(new_data["trade_date"].unique()) & set(existing["trade_date"].unique())
    if overlap:
        existing = existing[~existing["trade_date"].isin(overlap)]

    all_cols = list(dict.fromkeys(list(existing.columns) + [c for c in new_data.columns if c not in existing.columns]))
    new_data = new_data.reindex(columns=all_cols, fill_value=0)
    for c in all_cols:
        if c not in existing.columns:
            existing[c] = 0
    existing = existing.reindex(columns=all_cols, fill_value=0)

    combined = pd.concat([existing, new_data], ignore_index=True)
    combined = combined.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    combined.to_parquet(str(PARQUET_PATH), index=False, engine="pyarrow")

    log.info("Feature parquet updated: %d new rows, total %d rows",
             len(new_data), len(combined))
    return {
        "status": "ok",
        "new_rows": len(new_data),
        "total_rows": len(combined),
        "since": str(since_date),
        "until": str(until_date),
    }


# ---------------------------------------------------------------------------
# Sync status
# ---------------------------------------------------------------------------
def get_sync_status() -> dict:
    """获取当前同步状态摘要。"""
    engine = _get_engine()
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        row = conn.execute(
            sql_text("""
                SELECT
                    MAX(trade_date) AS latest_date,
                    MIN(trade_date) AS earliest_date,
                    COUNT(DISTINCT symbol) AS symbol_count,
                    COUNT(*) AS total_rows
                FROM stock_daily_latest
            """)
        ).fetchone()

    qroot = _find_qlib_root()
    cal_info = {}
    if qroot:
        cal_path = qroot / "calendars" / "day.txt"
        if cal_path.exists():
            lines = cal_path.read_text().strip().splitlines()
            cal_info = {
                "calendar_start": lines[0].strip() if lines else None,
                "calendar_end": lines[-1].strip() if lines else None,
                "calendar_days": len(lines),
            }
        feat_dir = qroot / "features"
        if feat_dir.exists():
            cal_info["qlib_stocks"] = len(list(feat_dir.iterdir()))

    return {
        "pg_latest_date": row[0].isoformat() if row[0] else None,
        "pg_earliest_date": row[1].isoformat() if row[1] else None,
        "pg_symbol_count": row[2],
        "pg_total_rows": row[3],
        "investment_data_dir": str(INVESTMENT_DATA_DIR),
        "investment_data_exists": INVESTMENT_DATA_DIR.exists(),
        **cal_info,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="QuantMind 统一日常数据同步")
    parser.add_argument("--market", default="A", help="市场 (A/HK/US)")
    parser.add_argument("--incremental", action="store_true", default=True,
                        help="增量模式（只补缺失天数）")
    parser.add_argument("--full", action="store_true", help="全量模式（重写）")
    parser.add_argument("--symbols", default="", help="指定股票（逗号分隔）")
    parser.add_argument("--no-qlib-bin", action="store_true", help="不更新 qlib bin")
    parser.add_argument("--no-calibrate", action="store_true", help="不校准指标")
    parser.add_argument("--calibrate-days", type=int, default=90, help="指标校准回溯天数")
    parser.add_argument("--update-investment-data", action="store_true",
                        help="仅更新 investment_data（下载最新 qlib_bin）")
    parser.add_argument("--calibrate-only", action="store_true", help="仅校准指标")
    parser.add_argument("--status", action="store_true", help="显示同步状态")
    args = parser.parse_args()

    if args.status:
        import json
        status = get_sync_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.update_investment_data:
        result = update_investment_data()
        log.info("Investment data updated: %s", result)
        return 0

    if args.calibrate_only:
        engine = _get_engine()
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
        _calibrate_indicators(engine, symbols=symbols, days=args.calibrate_days)
        return 0

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
    incremental = not args.full

    result = run_sync(
        market=args.market,
        symbols=symbols,
        incremental=incremental,
        update_qlib=not args.no_qlib_bin,
        calibrate=not args.no_calibrate,
        calibrate_days=args.calibrate_days,
    )

    log.info("=" * 60)
    log.info("Sync result:")
    log.info("  Mode: %s", result["mode"])
    log.info("  investment_data: %d symbols", result["investment_data_synced"])
    log.info("  baostock: %d symbols", result["baostock_synced"])
    log.info("  akshare: %d symbols", result["akshare_synced"])
    log.info("  eltdx: %d symbols", result["eltdx_synced"])
    log.info("  qlib_bin updated: %d symbols", result["qlib_bin_updated"])
    log.info("  indicators calibrated: %s", result["indicators_calibrated"])
    if result["errors"]:
        log.warning("  errors: %d", len(result["errors"]))
        for e in result["errors"][:10]:
            log.warning("    - %s", e)
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        log.error("FATAL: %s", e, exc_info=True)
        sys.exit(1)
