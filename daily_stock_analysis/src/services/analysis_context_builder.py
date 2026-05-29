# -*- coding: utf-8 -*-
"""Assembler for the internal AnalysisContextPack P2 contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from src.schemas.analysis_context_pack import (
    AnalysisContextBlock,
    AnalysisContextItem,
    AnalysisContextPack,
    AnalysisSubject,
    ContextFieldStatus,
    DataQuality,
)


_REALTIME_OVERLAY_WARNING = "intraday_realtime_overlay"
_REALTIME_FALLBACK_WARNING = "realtime_provider_fallback"
_FUNDAMENTAL_FAILED_REASON = "fundamental_pipeline_failed"


@dataclass(frozen=True)
class PipelineAnalysisArtifacts:
    """Artifacts already fetched by the stock analysis pipeline."""

    code: str
    stock_name: str
    market: str
    phase: Optional[Dict[str, Any]]
    base_context: Dict[str, Any]
    enhanced_context: Dict[str, Any]
    realtime_quote: Optional[Any]
    trend_result: Optional[Any]
    chip_data: Optional[Any]
    fundamental_context: Optional[Dict[str, Any]]
    news_context: Optional[str]
    news_result_count: Optional[int]
    metadata: Dict[str, Any]


class AnalysisContextBuilder:
    """Build AnalysisContextPack from existing pipeline artifacts only."""

    @staticmethod
    def build(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextPack:
        metadata = dict(artifacts.metadata or {})
        if artifacts.news_result_count is not None:
            metadata["news_result_count"] = artifacts.news_result_count

        blocks: Dict[str, AnalysisContextBlock] = {}
        data_quality_warnings: List[str] = []

        blocks["quote"] = _build_quote_block(artifacts)
        blocks["daily_bars"] = _build_daily_bars_block(artifacts)
        technical_block, technical_warnings = _build_technical_block(artifacts)
        blocks["technical"] = technical_block
        data_quality_warnings.extend(technical_warnings)
        blocks["chip"] = _build_chip_block(artifacts)
        blocks["fundamentals"] = _build_fundamentals_block(artifacts)
        blocks["news"] = _build_news_block(artifacts)

        return AnalysisContextPack(
            subject=AnalysisSubject(
                code=artifacts.code,
                stock_name=artifacts.stock_name or None,
                market=artifacts.market or None,
            ),
            phase=artifacts.phase,
            blocks=blocks,
            data_quality=DataQuality(warnings=data_quality_warnings),
            metadata=metadata,
        )

    @staticmethod
    def build_batch(items: Sequence[PipelineAnalysisArtifacts]) -> List[AnalysisContextPack]:
        return [AnalysisContextBuilder.build(item) for item in items]


def _build_quote_block(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextBlock:
    quote = _to_dict(artifacts.realtime_quote)
    if not quote:
        return AnalysisContextBlock(
            status=ContextFieldStatus.MISSING,
            items={
                "quote": AnalysisContextItem(
                    status=ContextFieldStatus.MISSING,
                    missing_reason="realtime_quote_missing",
                )
            },
        )

    source = _source_text(quote.get("source"))
    status = ContextFieldStatus.AVAILABLE
    warnings: List[str] = []
    fallback_from = _metadata_value(
        quote,
        "fallback_from",
        "quote_fallback_from",
        "realtime_fallback_from",
        "fallback_provider",
    ) or _metadata_value(
        artifacts.metadata,
        "quote_fallback_from",
        "realtime_fallback_from",
        "fallback_from",
    )

    if _has_explicit_quote_stale_marker(artifacts, quote):
        status = ContextFieldStatus.STALE
        warnings.append("quote_stale")
    elif source == "fallback":
        status = ContextFieldStatus.FALLBACK
        if fallback_from is None:
            warnings.append(_REALTIME_FALLBACK_WARNING)

    items = {
        key: AnalysisContextItem(
            status=status,
            value=value,
            source=source,
            fallback_from=fallback_from if status == ContextFieldStatus.FALLBACK else None,
            warnings=list(warnings),
        )
        for key, value in quote.items()
        if value is not None
    }
    return AnalysisContextBlock(
        status=status,
        items=items,
        source=source,
        warnings=warnings,
        metadata=_quote_metadata(artifacts, quote),
    )


def _build_daily_bars_block(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextBlock:
    context = artifacts.base_context or {}
    date_value = context.get("date")
    metadata = {
        key: value
        for key, value in {
            "date": date_value,
            "data_missing": bool(context.get("data_missing")),
        }.items()
        if value not in (None, "")
    }
    if context.get("data_missing"):
        return AnalysisContextBlock(
            status=ContextFieldStatus.MISSING,
            items={
                "today": AnalysisContextItem(
                    status=ContextFieldStatus.MISSING,
                    value=context.get("today") or None,
                    missing_reason="daily_bars_missing",
                    metadata={"date": date_value} if date_value else {},
                ),
                "yesterday": AnalysisContextItem(
                    status=ContextFieldStatus.MISSING,
                    value=context.get("yesterday") or None,
                    missing_reason="daily_bars_missing",
                ),
            },
            source="storage.get_analysis_context",
            metadata=metadata,
        )

    items: Dict[str, AnalysisContextItem] = {}
    for key in ("today", "yesterday"):
        value = context.get(key)
        items[key] = AnalysisContextItem(
            status=ContextFieldStatus.AVAILABLE if value else ContextFieldStatus.MISSING,
            value=value or None,
            source="storage.get_analysis_context",
            missing_reason=None if value else f"{key}_missing",
        )
    if date_value:
        items["date"] = AnalysisContextItem(
            status=ContextFieldStatus.AVAILABLE,
            value=date_value,
            source="storage.get_analysis_context",
            metadata={"date": date_value},
        )

    bar_statuses = [items[key].status for key in ("today", "yesterday")]
    if all(status == ContextFieldStatus.AVAILABLE for status in bar_statuses):
        block_status = ContextFieldStatus.AVAILABLE
    elif any(status == ContextFieldStatus.AVAILABLE for status in bar_statuses):
        block_status = ContextFieldStatus.PARTIAL
    else:
        block_status = ContextFieldStatus.MISSING
    return AnalysisContextBlock(
        status=block_status,
        items=items,
        source="storage.get_analysis_context",
        metadata=metadata,
    )


def _build_technical_block(
    artifacts: PipelineAnalysisArtifacts,
) -> tuple[AnalysisContextBlock, List[str]]:
    trend = _to_dict(artifacts.trend_result)
    if not trend:
        return (
            AnalysisContextBlock(
                status=ContextFieldStatus.MISSING,
                items={
                    "trend_result": AnalysisContextItem(
                        status=ContextFieldStatus.MISSING,
                        missing_reason="trend_result_missing",
                    )
                },
            ),
            [],
        )

    has_realtime_overlay = _has_realtime_overlay(artifacts.enhanced_context)
    warnings = [_REALTIME_OVERLAY_WARNING] if has_realtime_overlay else []
    block_status = (
        ContextFieldStatus.PARTIAL
        if has_realtime_overlay
        else ContextFieldStatus.AVAILABLE
    )
    items: Dict[str, AnalysisContextItem] = {
        "trend_result": AnalysisContextItem(
            status=ContextFieldStatus.AVAILABLE,
            value=trend,
            warnings=list(warnings),
        )
    }
    if has_realtime_overlay:
        items["intraday_overlay"] = AnalysisContextItem(
            status=ContextFieldStatus.ESTIMATED,
            value=(artifacts.enhanced_context or {}).get("today"),
            warnings=list(warnings),
        )

    return (
        AnalysisContextBlock(
            status=block_status,
            items=items,
            warnings=warnings,
            metadata={
                "overlay_source": _realtime_overlay_source(artifacts.enhanced_context)
            },
        ),
        warnings,
    )


def _build_chip_block(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextBlock:
    chip = _to_dict(artifacts.chip_data)
    if not chip:
        not_supported = bool((artifacts.metadata or {}).get("chip_not_supported"))
        status = (
            ContextFieldStatus.NOT_SUPPORTED
            if not_supported
            else ContextFieldStatus.MISSING
        )
        return AnalysisContextBlock(
            status=status,
            items={
                "chip_distribution": AnalysisContextItem(
                    status=status,
                    missing_reason=(
                        "chip_not_supported"
                        if not_supported
                        else "chip_distribution_missing"
                    ),
                )
            },
        )

    source = _source_text(chip.get("source"))
    return AnalysisContextBlock(
        status=ContextFieldStatus.AVAILABLE,
        items={
            key: AnalysisContextItem(
                status=ContextFieldStatus.AVAILABLE,
                value=value,
                source=source,
            )
            for key, value in chip.items()
            if value is not None
        },
        source=source,
        metadata={"date": chip.get("date")} if chip.get("date") else {},
    )


def _build_fundamentals_block(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextBlock:
    context = artifacts.fundamental_context if isinstance(artifacts.fundamental_context, dict) else None
    if not context:
        return AnalysisContextBlock(
            status=ContextFieldStatus.MISSING,
            items={
                "fundamental_context": AnalysisContextItem(
                    status=ContextFieldStatus.MISSING,
                    missing_reason="fundamental_context_missing",
                )
            },
        )

    raw_status = str(context.get("status") or "").strip().lower()
    status = _fundamental_status(raw_status)
    missing_reason = (
        _FUNDAMENTAL_FAILED_REASON
        if raw_status == "failed"
        else ("fundamentals_not_supported" if raw_status == "not_supported" else None)
    )
    coverage = context.get("coverage") if isinstance(context.get("coverage"), dict) else {}
    source_chain = context.get("source_chain") if isinstance(context.get("source_chain"), list) else []
    source = _source_from_chain(source_chain)
    metadata = {
        "status": raw_status or None,
        "coverage": coverage,
        "source_chain": source_chain,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, {}, [])}

    return AnalysisContextBlock(
        status=status,
        items={
            "status": AnalysisContextItem(
                status=status,
                value=raw_status or None,
                source=source,
                missing_reason=missing_reason,
            ),
            "coverage": AnalysisContextItem(
                status=_fundamental_payload_status(status, bool(coverage)),
                value=coverage or None,
                source=source,
                missing_reason=_fundamental_payload_missing_reason(
                    raw_status,
                    bool(coverage),
                    "fundamental_coverage_missing",
                ),
            ),
            "source_chain": AnalysisContextItem(
                status=_fundamental_payload_status(status, bool(source_chain)),
                value=source_chain or None,
                source=source,
                missing_reason=_fundamental_payload_missing_reason(
                    raw_status,
                    bool(source_chain),
                    "fundamental_source_chain_missing",
                ),
            ),
        },
        source=source,
        metadata=metadata,
    )


def _build_news_block(artifacts: PipelineAnalysisArtifacts) -> AnalysisContextBlock:
    content = (artifacts.news_context or "").strip()
    metadata: Dict[str, Any] = {}
    if artifacts.news_result_count is not None:
        metadata["news_result_count"] = artifacts.news_result_count

    if not content:
        return AnalysisContextBlock(
            status=ContextFieldStatus.MISSING,
            items={
                "content": AnalysisContextItem(
                    status=ContextFieldStatus.MISSING,
                    missing_reason="news_context_missing",
                )
            },
            metadata=metadata,
        )

    return AnalysisContextBlock(
        status=ContextFieldStatus.AVAILABLE,
        items={
            "content": AnalysisContextItem(
                status=ContextFieldStatus.AVAILABLE,
                value=content,
            )
        },
        metadata=metadata,
    )


def _to_dict(value: Optional[Any]) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if not isinstance(result, Mapping):
            raise TypeError(
                f"{type(value).__name__}.to_dict() must return a mapping"
            )
        return dict(result)
    value_dict = getattr(value, "__dict__", None)
    if isinstance(value_dict, dict):
        return dict(value_dict)
    return {}


def _source_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        value = enum_value
    text = str(value).strip()
    return text or None


def _metadata_value(metadata: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = (metadata or {}).get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _has_explicit_quote_stale_marker(
    artifacts: PipelineAnalysisArtifacts,
    quote: Dict[str, Any],
) -> bool:
    metadata = artifacts.metadata or {}
    for key in (
        "price_stale",
        "quote_stale",
        "quote_stale_seconds",
        "stale_seconds",
    ):
        if bool(metadata.get(key)) or bool(quote.get(key)):
            return True
    return False


def _quote_metadata(
    artifacts: PipelineAnalysisArtifacts,
    quote: Dict[str, Any],
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key in (
        "price_stale",
        "quote_stale",
        "quote_stale_seconds",
        "stale_seconds",
    ):
        value = (artifacts.metadata or {}).get(key)
        if value is None:
            value = quote.get(key)
        if value is not None:
            metadata[key] = value
    return metadata


def _has_realtime_overlay(enhanced_context: Dict[str, Any]) -> bool:
    today = (enhanced_context or {}).get("today")
    if not isinstance(today, dict):
        return False
    data_source = today.get("data_source") or today.get("dataSource")
    return isinstance(data_source, str) and data_source.startswith("realtime:")


def _realtime_overlay_source(enhanced_context: Dict[str, Any]) -> Optional[str]:
    today = (enhanced_context or {}).get("today")
    if not isinstance(today, dict):
        return None
    value = today.get("data_source") or today.get("dataSource")
    return value if isinstance(value, str) and value else None


def _fundamental_status(status: str) -> ContextFieldStatus:
    if status in {"ok", "available"}:
        return ContextFieldStatus.AVAILABLE
    if status == "not_supported":
        return ContextFieldStatus.NOT_SUPPORTED
    if status == "partial":
        return ContextFieldStatus.PARTIAL
    return ContextFieldStatus.MISSING


def _fundamental_payload_status(
    block_status: ContextFieldStatus,
    has_payload: bool,
) -> ContextFieldStatus:
    if has_payload:
        return block_status
    if block_status == ContextFieldStatus.NOT_SUPPORTED:
        return ContextFieldStatus.NOT_SUPPORTED
    return ContextFieldStatus.MISSING


def _fundamental_payload_missing_reason(
    raw_status: str,
    has_payload: bool,
    missing_reason: str,
) -> Optional[str]:
    if raw_status == "failed":
        return _FUNDAMENTAL_FAILED_REASON
    if raw_status == "not_supported":
        return "fundamentals_not_supported"
    if has_payload:
        return None
    return missing_reason


def _source_from_chain(source_chain: Any) -> Optional[str]:
    if not isinstance(source_chain, list) or not source_chain:
        return None
    first = source_chain[0]
    if isinstance(first, dict):
        return _source_text(first.get("provider") or first.get("source"))
    return _source_text(first)
