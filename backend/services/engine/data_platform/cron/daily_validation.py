"""
数据平台每日校验 cron
========================

功能：
1. 每日采样 N 只股票（默认 50），逐市场调用 FieldAggregator.fetch(daily_kline) 拉取最近 5 天数据
2. 对比 adj_factor 是否在源间一致
3. 检测最近 5 天是否有“缺失交易日”
4. 异常写入 data_quality_alerts + 通知 admin

使用：
    docker exec quantmind python -m backend.services.engine.data_platform.cron.daily_validation \
        --market A --sample 50

建议 crontab（容器外宿主机）：
    30 18 * * * docker exec quantmind python -m backend.services.engine.data_platform.cron.daily_validation \
        --market A --sample 50 >> /var/log/quantmind/data_validation.log 2>&1
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


def _normalize_a_symbol(s: str) -> str:
    """SH600519 / sh600519 / 600519 → 600519.SH"""
    s = s.upper().strip()
    if "." in s:
        return s
    if len(s) >= 8 and s[:2] in ("SH", "SZ", "BJ"):
        return f"{s[2:]}.{s[:2]}"
    if len(s) == 6 and s.isdigit():
        if s.startswith(("600", "601", "603", "605", "688", "689", "900")):
            return f"{s}.SH"
        if s.startswith(("83", "87", "92")):
            return f"{s}.BJ"
        return f"{s}.SZ"
    return s


def _load_symbols(market: str, sample_size: int) -> list[str]:
    """从 stock_daily_latest（A 股）或常用列表采样。"""
    if market == "A":
        try:
            from sqlalchemy import create_engine, text
            from backend.services.engine.data_platform.alert_service import _resolve_db_url
            engine = create_engine(_resolve_db_url(), pool_pre_ping=True)
            with engine.begin() as conn:
                rows = conn.execute(
                    text(
                        "SELECT symbol FROM ("
                        "  SELECT DISTINCT symbol FROM stock_daily_latest "
                        "  WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'"
                        ") s ORDER BY random() LIMIT :n"
                    ),
                    {"n": sample_size},
                ).fetchall()
                return [_normalize_a_symbol(r[0]) for r in rows]
        except Exception as exc:
            logger.warning("sample from db failed: %s; fallback to static", exc)
        return ["600519.SH", "000001.SZ", "601318.SH", "000858.SZ", "600036.SH"][:sample_size]
    if market == "HK":
        return ["00700.HK", "09988.HK", "00388.HK", "01299.HK"][:sample_size]
    if market == "US":
        return ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"][:sample_size]
    return []


def validate_market(market: str, sample_size: int, lookback_days: int = 5) -> dict[str, Any]:
    """执行单个市场的校验。"""
    from backend.services.engine.data_platform.adapters import register_all
    from backend.services.engine.data_platform.aggregator import (
        FieldAggregator, FieldRoutingTable,
    )
    from backend.services.engine.data_platform.alert_service import get_alert_service
    from backend.services.engine.data_platform.cleaner import DataCleaner
    from backend.services.engine.data_platform.monitor import get_monitor
    from backend.services.engine.data_platform.registry import get_registry

    register_all()
    agg = FieldAggregator(
        registry=get_registry(),
        routing=FieldRoutingTable(),
        monitor=get_monitor(),
        cleaner=DataCleaner(),
    )
    alerts = get_alert_service()

    end = date.today()
    start = end - timedelta(days=lookback_days + 7)  # 留 weekend buffer
    symbols = _load_symbols(market, sample_size)
    logger.info("market=%s sampling %d symbols", market, len(symbols))

    stats = {
        "total": len(symbols),
        "ok": 0,
        "empty": 0,
        "failed": 0,
        "adj_factor_mismatch": 0,
        "missing_days": 0,
    }

    for sym in symbols:
        try:
            res = agg.fetch(
                market=market, field="daily_kline", symbol=sym,
                start=start, end=end,
            )
            df = res.data
            if df is None or df.empty:
                stats["empty"] += 1
                continue
            stats["ok"] += 1

            # 检查 adj_factor 是否突变（同一天与历史均值差异 > 5%）
            if "adj_factor" in df.columns and len(df) > 3:
                af = df["adj_factor"].dropna()
                if not af.empty:
                    last_af = float(af.iloc[-1])
                    prev_mean = float(af.iloc[:-1].mean() or 1.0)
                    if prev_mean > 0 and abs(last_af - prev_mean) / prev_mean > 0.05:
                        stats["adj_factor_mismatch"] += 1
                        alerts.write_alert(
                            alert_type="adj_factor_jump",
                            severity="warning",
                            message=f"{sym} adj_factor 跳变: last={last_af:.4f} prev_mean={prev_mean:.4f}",
                            market=market, field="daily_kline",
                            source=res.source_used, symbol=sym,
                            details={"last": last_af, "prev_mean": prev_mean},
                        )

            # 检查最近 N 天的覆盖（粗略：>=lookback_days * 5/7）
            try:
                recent = df[df["trade_date"] >= (end - timedelta(days=lookback_days)).strftime("%Y-%m-%d")]
            except Exception:
                recent = df.tail(lookback_days)
            expected = max(1, int(lookback_days * 5 / 7))
            if len(recent) < expected - 1:
                stats["missing_days"] += 1
                alerts.write_alert(
                    alert_type="missing_trading_days",
                    severity="warning",
                    message=f"{sym} 最近 {lookback_days} 天仅返回 {len(recent)} 行（预期≥{expected}）",
                    market=market, field="daily_kline",
                    source=res.source_used, symbol=sym,
                    details={"returned": len(recent), "expected": expected},
                )
        except Exception as exc:
            stats["failed"] += 1
            logger.warning("validate %s/%s failed: %s", market, sym, exc)
            # 单 symbol 失败不写告警（避免噪音）；连续失败由 HealthMonitor 触发
            continue

    failure_rate = (stats["empty"] + stats["failed"]) / max(1, stats["total"])
    if failure_rate > 0.30:
        alerts.write_alert(
            alert_type="market_validation_failed",
            severity="error",
            message=f"市场 {market} 数据校验失败率 {failure_rate:.0%}",
            market=market, field="daily_kline",
            details=stats,
        )

    logger.info("market=%s done: %s", market, stats)
    return stats


def main():
    _setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default="A", choices=["A", "HK", "US", "ALL"])
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--lookback", type=int, default=5)
    args = parser.parse_args()

    markets = ["A", "HK", "US"] if args.market == "ALL" else [args.market]
    overall: dict[str, Any] = {}
    for m in markets:
        overall[m] = validate_market(m, args.sample, args.lookback)

    logger.info("validation overall=%s", overall)
    # 退出码：任一市场严重失败返回 2
    for m, st in overall.items():
        if (st["empty"] + st["failed"]) / max(1, st["total"]) > 0.5:
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
