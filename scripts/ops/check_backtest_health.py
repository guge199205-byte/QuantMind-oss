#!/usr/bin/env python3
"""Backtest health checker.

检查项：
1) Worker 日志是否存在失败痕迹（ERROR/Traceback/Task failed）
2) 最近回测任务是否有 succeeded 记录
3) 关键告警计数（$close nan / Mean of empty slice / invalid divide）
4) 最近回测落库状态与 signal_meta 质量
5) API 日志是否出现默认 DB 密码告警
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str  # PASS / WARN / FAIL / SKIP
    detail: str


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_tail_lines(path: Path, max_lines: int) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-max_lines:]


def count_patterns(lines: List[str], pattern: str) -> int:
    regex = re.compile(pattern)
    return sum(1 for line in lines if regex.search(line))


def build_db_url() -> Optional[str]:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        if db_url.startswith("postgresql+asyncpg://"):
            return db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        if db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if db_url.startswith("postgres://"):
            return db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        return db_url

    host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
    port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT") or "5432"
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME")
    if not (host and user and db_name):
        return None
    return (
        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{db_name}"
    )


def query_recent_runs(limit: int) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    try:
        from sqlalchemy import create_engine, text
    except Exception as exc:  # pragma: no cover - dependency issue
        return f"sqlalchemy unavailable: {exc}", []

    db_url = build_db_url()
    if not db_url:
        return "missing db env vars", []

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT backtest_id, status, created_at, config_json
                    FROM qlib_backtest_runs
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return None, [dict(r) for r in rows]
    except Exception as exc:
        return str(exc), []


def check_worker_errors(worker_lines: List[str]) -> CheckResult:
    fail_count = count_patterns(
        worker_lines,
        r"(ERROR|CRITICAL|Traceback|Task .* failed|raised unexpected)",
    )
    if fail_count > 0:
        return CheckResult("Worker失败痕迹", "FAIL", f"发现 {fail_count} 条错误/失败记录")
    return CheckResult("Worker失败痕迹", "PASS", "未发现 ERROR/Traceback/Task failed")


def check_recent_success(worker_lines: List[str], min_success: int) -> CheckResult:
    success_count = count_patterns(worker_lines, r"Task .* succeeded")
    if success_count < min_success:
        return CheckResult(
            "最近任务成功数",
            "FAIL",
            f"仅发现 {success_count} 条 succeeded（期望 >= {min_success}）",
        )
    return CheckResult("最近任务成功数", "PASS", f"发现 {success_count} 条 succeeded")


def check_warning_counts(worker_lines: List[str]) -> CheckResult:
    close_nan = count_patterns(worker_lines, r"\$close field data contains nan")
    mean_empty = count_patterns(worker_lines, r"Mean of empty slice")
    invalid_div = count_patterns(worker_lines, r"invalid value encountered")
    total = close_nan + mean_empty + invalid_div
    if total == 0:
        return CheckResult("关键数值告警", "PASS", "未发现 close-nan/empty-slice/divide 告警")
    return CheckResult(
        "关键数值告警",
        "WARN",
        (
            f"close_nan={close_nan}, mean_empty={mean_empty}, "
            f"invalid_divide={invalid_div}"
        ),
    )


def check_db_runs(
    rows: List[Dict[str, Any]], min_dates: int, min_instruments: int, max_nan_ratio: float
) -> CheckResult:
    if not rows:
        return CheckResult("最近回测落库", "SKIP", "未读到 qlib_backtest_runs 记录")

    bad_status = [r["backtest_id"] for r in rows if str(r.get("status")) != "completed"]
    if bad_status:
        return CheckResult("最近回测落库", "FAIL", f"存在非 completed: {bad_status[:3]}")

    missing_meta = []
    weak_meta = []
    for r in rows:
        cfg = r.get("config_json") or {}
        sm = cfg.get("signal_meta")
        if not isinstance(sm, dict):
            missing_meta.append(r["backtest_id"])
            continue
        if sm.get("source") == "pred_pkl":
            date_count = int(sm.get("date_count") or 0)
            instrument_count = int(sm.get("instrument_count") or 0)
            nan_ratio = float(sm.get("score_nan_ratio") or 0.0)
            if (
                date_count < min_dates
                or instrument_count < min_instruments
                or nan_ratio > max_nan_ratio
            ):
                weak_meta.append(
                    (
                        r["backtest_id"],
                        date_count,
                        instrument_count,
                        nan_ratio,
                    )
                )

    if missing_meta:
        return CheckResult("最近回测落库", "WARN", f"缺少 signal_meta: {missing_meta[:3]}")
    if weak_meta:
        sample = weak_meta[0]
        return CheckResult(
            "最近回测落库",
            "WARN",
            (
                "signal_meta 质量偏弱: "
                f"id={sample[0]}, date={sample[1]}, inst={sample[2]}, nan={sample[3]:.2%}"
            ),
        )
    return CheckResult("最近回测落库", "PASS", f"最近 {len(rows)} 条 completed 且 signal_meta 合格")


def check_default_db_password(api_lines: List[str]) -> CheckResult:
    count = count_patterns(api_lines, r"Using default DB_PASSWORD")
    if count > 0:
        return CheckResult(
            "默认DB密码告警",
            "WARN",
            f"检测到 {count} 条 default DB_PASSWORD 告警",
        )
    return CheckResult("默认DB密码告警", "PASS", "未发现默认 DB 密码告警")


def print_results(results: List[CheckResult]) -> int:
    order = {"FAIL": 3, "WARN": 2, "PASS": 1, "SKIP": 0}
    worst = max((order[r.status] for r in results), default=0)
    for r in results:
        print(f"[{r.status}] {r.name}: {r.detail}")
    if worst >= 3:
        print("OVERALL: FAIL")
        return 2
    if worst == 2:
        print("OVERALL: WARN")
        return 1
    print("OVERALL: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 QuantMind 回测链路健康状态")
    parser.add_argument("--worker-log", default="logs/backtest_worker.log")
    parser.add_argument("--api-log", default="logs/api.log")
    parser.add_argument("--tail-lines", type=int, default=3000)
    parser.add_argument("--recent-runs", type=int, default=3)
    parser.add_argument("--min-success", type=int, default=1)
    parser.add_argument("--min-dates", type=int, default=60)
    parser.add_argument("--min-instruments", type=int, default=300)
    parser.add_argument("--max-nan-ratio", type=float, default=0.05)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    worker_lines = read_tail_lines(ROOT / args.worker_log, args.tail_lines)
    api_lines = read_tail_lines(ROOT / args.api_log, args.tail_lines)
    db_err, db_rows = query_recent_runs(args.recent_runs)

    results: List[CheckResult] = [
        check_worker_errors(worker_lines),
        check_recent_success(worker_lines, args.min_success),
        check_warning_counts(worker_lines),
        check_default_db_password(api_lines),
    ]
    if db_err:
        results.append(CheckResult("最近回测落库", "SKIP", f"DB检查跳过: {db_err}"))
    else:
        results.append(
            check_db_runs(
                db_rows,
                min_dates=args.min_dates,
                min_instruments=args.min_instruments,
                max_nan_ratio=args.max_nan_ratio,
            )
        )

    return print_results(results)


if __name__ == "__main__":
    sys.exit(main())

