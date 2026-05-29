# -*- coding: utf-8 -*-
"""Tests for #1389 P3 AnalysisContextPack prompt summaries."""

from __future__ import annotations

from src.analysis_context_pack_prompt import format_analysis_context_pack_prompt_section
from src.schemas.analysis_context_pack import (
    AnalysisContextBlock,
    AnalysisContextItem,
    AnalysisContextPack,
    AnalysisSubject,
    ContextFieldStatus,
    DataQuality,
)


def _pack() -> AnalysisContextPack:
    return AnalysisContextPack(
        subject=AnalysisSubject(code="600519", stock_name="贵州茅台", market="cn"),
        blocks={
            "quote": AnalysisContextBlock(
                status=ContextFieldStatus.FALLBACK,
                source="fallback",
                warnings=["realtime_provider_fallback"],
                items={
                    "price": AnalysisContextItem(
                        status=ContextFieldStatus.FALLBACK,
                        value=1880.0,
                        source="fallback",
                        fallback_from="primary_realtime_provider",
                    )
                },
            ),
            "technical": AnalysisContextBlock(
                status=ContextFieldStatus.PARTIAL,
                warnings=["intraday_realtime_overlay"],
                items={
                    "trend_result": AnalysisContextItem(
                        status=ContextFieldStatus.AVAILABLE,
                        value={"trend_status": "多头排列", "ma5": 1800.0},
                    ),
                    "intraday_overlay": AnalysisContextItem(
                        status=ContextFieldStatus.ESTIMATED,
                        value={"close": 1880.0},
                    ),
                },
            ),
            "news": AnalysisContextBlock(
                status=ContextFieldStatus.MISSING,
                items={
                    "content": AnalysisContextItem(
                        status=ContextFieldStatus.MISSING,
                        value="完整新闻正文不应进入摘要",
                        missing_reason="news_context_missing",
                    )
                },
            ),
            "fundamentals": AnalysisContextBlock(
                status=ContextFieldStatus.AVAILABLE,
                metadata={
                    "coverage": {
                        "valuation": "ok",
                        "access_token": "secret-token",
                    }
                },
                items={
                    "coverage": AnalysisContextItem(
                        status=ContextFieldStatus.AVAILABLE,
                        value={"valuation": "ok", "access_token": "secret-token"},
                    )
                },
            ),
        },
        data_quality=DataQuality(warnings=["intraday_realtime_overlay"]),
        metadata={
            "query_id": "q-1",
            "trigger_source": "api",
            "news_result_count": 3,
            "webhook_url": "https://hooks.example.test/secret",
        },
    )


def test_empty_or_invalid_pack_returns_empty_section() -> None:
    assert format_analysis_context_pack_prompt_section(None) == ""
    assert format_analysis_context_pack_prompt_section({}) == ""
    assert format_analysis_context_pack_prompt_section("not-pack") == ""


def test_chinese_summary_renders_low_sensitivity_pack_statuses() -> None:
    section = format_analysis_context_pack_prompt_section(_pack())

    assert "分析上下文包摘要" in section
    assert "600519" in section
    assert "贵州茅台" in section
    assert "行情: fallback" in section
    assert "技术: partial" in section
    assert "告警=realtime_provider_fallback" in section
    assert "新闻: missing" in section
    assert "news_context_missing" in section
    assert "新闻结果数：3" in section
    assert "intraday_realtime_overlay" in section


def test_english_summary_renders_readable_statuses() -> None:
    section = format_analysis_context_pack_prompt_section(
        _pack(),
        report_language="en",
    )

    assert "Analysis Context Pack Summary" in section
    assert "Subject: 600519 (贵州茅台)" in section
    assert "quote: fallback" in section
    assert "news: missing" in section
    assert "News result count: 3" in section


def test_summary_does_not_dump_values_or_sensitive_payloads() -> None:
    section = format_analysis_context_pack_prompt_section(_pack())

    assert "analysis_context_pack" not in section
    assert "完整新闻正文不应进入摘要" not in section
    assert "多头排列" not in section
    assert "secret-token" not in section
    assert "hooks.example.test" not in section
    assert "webhook_url" not in section
    assert "access_token" not in section
