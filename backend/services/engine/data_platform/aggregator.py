"""
字段路由 + 聚合层。

读取 config/data_sources/field_routing.yaml，按 (market, field) 找到 primary +
fallbacks 列表；调用 SourceRegistry 拉数据；可选地走 DataCleaner 清洗 + 共识投票。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field as _field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    SourceRateLimited,
)
from backend.services.engine.data_platform.monitor import HealthMonitor, get_monitor
from backend.services.engine.data_platform.registry import SourceRegistry, get_registry

logger = logging.getLogger(__name__)

def _default_routing_path() -> Path:
    env = os.getenv("QM_FIELD_ROUTING_PATH")
    if env:
        return Path(env)
    for candidate in (
        Path("/app/config/data_sources/field_routing.yaml"),         # 容器
        Path("/opt/quantmind/config/data_sources/field_routing.yaml"),  # 宿主
        Path(__file__).resolve().parents[4] / "config" / "data_sources" / "field_routing.yaml",
    ):
        if candidate.exists():
            return candidate
    return Path("/app/config/data_sources/field_routing.yaml")


DEFAULT_ROUTING_PATH = _default_routing_path()


@dataclass
class FieldRoute:
    market: str
    field: str
    tier: str
    primary: str
    fallbacks: list[str] = _field(default_factory=list)
    consensus: bool = False
    cleanup: bool = True

    @property
    def ordered_sources(self) -> list[str]:
        return [self.primary, *self.fallbacks]


@dataclass
class AggregationResult:
    market: str
    field: str
    data: pd.DataFrame
    source_used: str
    fallbacks_tried: list[str] = _field(default_factory=list)
    consensus_sources: list[str] = _field(default_factory=list)
    cleaning_report: dict[str, Any] = _field(default_factory=dict)


class FieldRoutingTable:
    """YAML 路由表加载/查询。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_ROUTING_PATH
        self._mtime = -1.0
        self._cfg: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if yaml is None:
            raise RuntimeError("PyYAML 未安装，无法加载 field_routing.yaml")
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        mtime = self.path.stat().st_mtime
        if mtime == self._mtime:
            return
        with open(self.path, encoding="utf-8") as f:
            self._cfg = yaml.safe_load(f) or {}
        self._mtime = mtime

    @property
    def consensus_threshold(self) -> float:
        return float(self._cfg.get("default_consensus_threshold", 0.02))

    @property
    def min_consensus_sources(self) -> int:
        return int(self._cfg.get("default_min_consensus_sources", 2))

    def get_route(self, market: str, field: str) -> FieldRoute:
        self._load()
        markets = self._cfg.get("markets", {})
        m = markets.get(market.upper())
        if not m:
            raise InvalidFieldRequest(f"市场未配置: {market}")
        f = m.get(field)
        if not f:
            raise InvalidFieldRequest(f"市场 {market} 未配置字段: {field}")
        return FieldRoute(
            market=market.upper(),
            field=field,
            tier=str(f.get("tier", "T1")),
            primary=str(f["primary"]),
            fallbacks=list(f.get("fallbacks", []) or []),
            consensus=bool(f.get("consensus", False)),
            cleanup=bool(f.get("cleanup", True)),
        )

    def list_markets(self) -> list[str]:
        self._load()
        return sorted((self._cfg.get("markets") or {}).keys())

    def list_fields(self, market: str) -> list[str]:
        self._load()
        m = (self._cfg.get("markets") or {}).get(market.upper(), {})
        return sorted(m.keys())


class FieldAggregator:
    """字段聚合层：按路由表调度数据源，处理 fallback 与共识投票。"""

    def __init__(
        self,
        *,
        registry: Optional[SourceRegistry] = None,
        routing: Optional[FieldRoutingTable] = None,
        monitor: Optional[HealthMonitor] = None,
        cleaner: Optional[Any] = None,  # 避免循环导入，运行时注入 DataCleaner
    ) -> None:
        self.registry = registry or get_registry()
        self.routing = routing or FieldRoutingTable()
        self.monitor = monitor or get_monitor()
        self.cleaner = cleaner

    # ---- 主入口 ----
    def fetch(
        self,
        *,
        market: str,
        field: str,
        symbol: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs: Any,
    ) -> AggregationResult:
        route = self.routing.get_route(market, field)

        if route.consensus:
            return self._fetch_with_consensus(route, symbol, start, end, **kwargs)
        return self._fetch_with_fallback(route, symbol, start, end, **kwargs)

    # ---- fallback 模式 ----
    def _fetch_with_fallback(
        self,
        route: FieldRoute,
        symbol: str,
        start: Optional[date],
        end: Optional[date],
        **kwargs: Any,
    ) -> AggregationResult:
        tried: list[str] = []
        for src in route.ordered_sources:
            try:
                df = self._call_adapter(src, route, symbol, start, end, **kwargs)
            except (DataUnavailable, SourceRateLimited, KeyError, InvalidFieldRequest) as exc:
                tried.append(src)
                if src != route.primary:
                    self.monitor.record_fallback(src, route.field)
                logger.info("source=%s field=%s skipped: %s", src, route.field, exc)
                continue
            except Exception as exc:  # noqa: BLE001
                tried.append(src)
                logger.warning("source=%s field=%s failed: %s", src, route.field, exc)
                continue

            if self.cleaner is not None and route.cleanup:
                df, report = self.cleaner.clean(df, market=route.market, field=route.field)
            else:
                report = {}

            return AggregationResult(
                market=route.market,
                field=route.field,
                data=df,
                source_used=src,
                fallbacks_tried=[s for s in tried if s != src],
                cleaning_report=report,
            )

        raise DataUnavailable(
            f"all sources exhausted for market={route.market} field={route.field}"
            f" symbol={symbol} tried={tried}"
        )

    # ---- 共识模式 ----
    def _fetch_with_consensus(
        self,
        route: FieldRoute,
        symbol: str,
        start: Optional[date],
        end: Optional[date],
        **kwargs: Any,
    ) -> AggregationResult:
        collected: list[tuple[str, pd.DataFrame]] = []
        for src in route.ordered_sources:
            try:
                df = self._call_adapter(src, route, symbol, start, end, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.info("consensus src=%s skipped: %s", src, exc)
                continue
            if df is None or df.empty:
                continue
            collected.append((src, df))

        if not collected:
            raise DataUnavailable(
                f"consensus failed: no source returned data for {route.market}/{route.field}/{symbol}"
            )

        # 不足 min_consensus_sources：退化为 fallback 模式（取第一个非空）
        if len(collected) < self.routing.min_consensus_sources:
            src, df = collected[0]
            if self.cleaner is not None and route.cleanup:
                df, report = self.cleaner.clean(df, market=route.market, field=route.field)
            else:
                report = {}
            return AggregationResult(
                market=route.market,
                field=route.field,
                data=df,
                source_used=src,
                fallbacks_tried=[s for s, _ in collected if s != src],
                consensus_sources=[src],
                cleaning_report=report,
            )

        # 共识投票：以 primary 为基准，比较 close 偏离
        threshold = self.routing.consensus_threshold
        base_src, base_df = collected[0]
        agreed: list[str] = [base_src]
        for src, df in collected[1:]:
            deviation = _consensus_deviation(base_df, df, on="close")
            self.monitor.record_consensus_deviation(src, route.field, deviation=deviation)
            if deviation <= threshold:
                agreed.append(src)

        # 用 agreed 中的源做行级中位数合并
        agreed_frames = [df for src, df in collected if src in agreed]
        merged = _merge_by_median(agreed_frames, base_src=base_src)

        if self.cleaner is not None and route.cleanup:
            merged, report = self.cleaner.clean(merged, market=route.market, field=route.field)
        else:
            report = {}

        return AggregationResult(
            market=route.market,
            field=route.field,
            data=merged,
            source_used=base_src,
            fallbacks_tried=[s for s, _ in collected if s not in agreed],
            consensus_sources=agreed,
            cleaning_report=report,
        )

    # ---- 适配器调用 ----
    def _call_adapter(
        self,
        source: str,
        route: FieldRoute,
        symbol: str,
        start: Optional[date],
        end: Optional[date],
        **kwargs: Any,
    ) -> pd.DataFrame:
        adapter = self.registry.get(source)
        if not adapter.supports(route.field, route.market):
            raise InvalidFieldRequest(
                f"adapter {source} does not support {route.market}/{route.field}"
            )

        t0 = time.time()
        try:
            df = self._dispatch(adapter, route.field, symbol, start, end, **kwargs)
        except (DataUnavailable, SourceRateLimited, InvalidFieldRequest):
            latency = (time.time() - t0) * 1000
            self.monitor.record_error(source, route.field, error="unavailable", latency_ms=latency)
            raise
        except Exception as exc:  # noqa: BLE001
            latency = (time.time() - t0) * 1000
            self.monitor.record_error(source, route.field, error=str(exc), latency_ms=latency)
            raise

        latency = (time.time() - t0) * 1000
        if df is None or df.empty:
            self.monitor.record_error(source, route.field, error="empty", latency_ms=latency)
            raise DataUnavailable(f"{source} returned empty for {route.field}")

        self.monitor.record_success(source, route.field, rows=len(df), latency_ms=latency)
        # 强制写入 source 列，便于下游审计
        df = df.copy()
        df["source"] = source
        return df

    @staticmethod
    def _dispatch(adapter, field, symbol, start, end, **kwargs):
        if field == "daily_kline":
            return adapter.fetch_daily(symbol, start, end, **kwargs)
        if field == "minute_kline":
            return adapter.fetch_minute(symbol, start, end, **kwargs)
        if field == "tick":
            return adapter.fetch_tick(symbol, start, **kwargs)
        if field == "realtime_quote":
            res = adapter.fetch_realtime(symbol)
            if res is None:
                return pd.DataFrame()
            if isinstance(res, pd.DataFrame):
                return res
            return pd.DataFrame([res])
        # 通用入口
        return adapter.fetch_field(field, symbol, start=start, end=end, **kwargs)


# ---------------------------------------------------------------------------
# 共识工具
# ---------------------------------------------------------------------------
def _consensus_deviation(base: pd.DataFrame, other: pd.DataFrame, *, on: str) -> float:
    """两个数据集在 `on` 列上的平均相对偏离（按 trade_date 对齐）。"""
    if base is None or other is None or base.empty or other.empty:
        return 1.0
    if on not in base.columns or on not in other.columns:
        return 1.0
    if "trade_date" not in base.columns or "trade_date" not in other.columns:
        return 1.0
    a = base[["trade_date", on]].copy()
    b = other[["trade_date", on]].copy()
    a["trade_date"] = pd.to_datetime(a["trade_date"])
    b["trade_date"] = pd.to_datetime(b["trade_date"])
    merged = a.merge(b, on="trade_date", suffixes=("_a", "_b"))
    if merged.empty:
        return 1.0
    valid = merged[(merged[f"{on}_a"] != 0) & (merged[f"{on}_b"].notna())]
    if valid.empty:
        return 1.0
    rel = ((valid[f"{on}_b"] - valid[f"{on}_a"]).abs() / valid[f"{on}_a"].abs()).mean()
    return float(rel)


def _merge_by_median(frames: list[pd.DataFrame], *, base_src: str) -> pd.DataFrame:
    """按 (symbol, trade_date) 合并多个 DataFrame，数值列取中位数。"""
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]

    keys = [c for c in ("symbol", "trade_date") if c in frames[0].columns]
    if not keys:
        return frames[0]

    combined = pd.concat(frames, ignore_index=True)
    numeric_cols = [
        c for c in combined.columns
        if c not in keys + ["source"] and pd.api.types.is_numeric_dtype(combined[c])
    ]
    if not numeric_cols:
        return combined.drop_duplicates(subset=keys, keep="first")

    grouped = combined.groupby(keys, as_index=False)[numeric_cols].median()
    # 保留 source 字段（来自 base_src）
    grouped["source"] = base_src
    return grouped.sort_values(keys).reset_index(drop=True)
