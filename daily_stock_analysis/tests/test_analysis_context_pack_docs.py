# -*- coding: utf-8 -*-
"""Contract checks for the AnalysisContextPack P0/P1 contract doc."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "analysis-context-pack.md"


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _section(doc: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in doc
    return doc.split(marker, 1)[1].split("\n## ", 1)[0]


def test_analysis_context_pack_doc_has_required_sections() -> None:
    doc = _read_doc()

    for heading in (
        "## 术语与边界",
        "## P0 范围与非目标",
        "## P1 内部契约",
        "## P2 Builder 契约",
        "## P3 Runtime Consumption",
        "## 字段质量状态",
        "## 现有状态映射",
        "## 七路径盘点",
        "## 源码锚点",
        "## 兼容与安全边界",
    ):
        assert heading in doc


def test_analysis_context_pack_doc_disambiguates_context_surfaces() -> None:
    section = _section(_read_doc(), "术语与边界")

    for token in (
        "`storage.get_analysis_context()`",
        "`enhanced_context`",
        "`analysis_history.context_snapshot`",
        "Agent executor message context",
        "Agent orchestrator `AgentContext`",
        "`AGENT_ARCH=single`",
        "`AGENT_ARCH=multi`",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p0_quality_states() -> None:
    section = _section(_read_doc(), "字段质量状态")

    for state in (
        "`available`",
        "`missing`",
        "`not_supported`",
        "`fallback`",
        "`stale`",
        "`estimated`",
        "`partial`",
    ):
        assert state in section
    assert "`fetch_failed`" not in section


def test_analysis_context_pack_doc_covers_seven_paths() -> None:
    section = _section(_read_doc(), "七路径盘点")

    for heading in (
        "### 普通分析",
        "### Agent",
        "### 告警",
        "### 持仓",
        "### 回测",
        "### 历史",
        "### 通知",
    ):
        assert heading in section


def test_analysis_context_pack_doc_records_agent_context_visibility() -> None:
    section = _section(_read_doc(), "七路径盘点")

    for token in (
        "`initial_context`",
        "`fundamental_context`",
        "不显式注入 `fundamental_context` 或 `trend_result`",
        "pre-fetched data",
        "不预注入 `fundamental_context`",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_non_goals_and_safety_boundaries() -> None:
    doc = _read_doc()

    for token in (
        "P1 已新增 `AnalysisContextPack` 内部 schema",
        "不新增 builder",
        "不接入 runtime",
        "不公开完整 pack",
        "不 pack 化 `market_review`",
        "`market_light`",
        "`fetch_failed` 与 `not_supported` 的细分留到 P5",
        "`analysis_history.context_snapshot.enhanced_context.date`",
        "完整 pack 不默认公开",
        "API key",
        "token",
        "cookie",
        "完整 webhook URL",
        "邮箱密码",
    ):
        assert token in doc


def test_analysis_context_pack_doc_defines_p1_schema_contract() -> None:
    section = _section(_read_doc(), "P1 内部契约")

    for token in (
        "`src/schemas/analysis_context_pack.py`",
        "`PACK_VERSION = \"1.0\"`",
        "`ContextFieldStatus`",
        "`AnalysisSubject`",
        "`AnalysisContextItem`",
        "`AnalysisContextBlock`",
        "`DataQuality`",
        "`AnalysisContextPack`",
        "`MarketPhaseContext.to_dict()`",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_block_catalog() -> None:
    section = _section(_read_doc(), "P1 内部契约")

    for token in (
        "P1 Block Catalog",
        "`quote`",
        "`daily_bars`",
        "`technical`",
        "`fundamentals`",
        "`news`",
        "`portfolio`",
        "`chip` / `capital_flow`",
        "`events` / `market_context`",
        "不重复新增 `identity` block",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_time_and_status_semantics() -> None:
    section = _section(_read_doc(), "P1 内部契约")

    for token in (
        "`AnalysisContextPack.created_at` 使用 `datetime`",
        "`model_dump(mode=\"json\")` 输出 ISO 8601",
        "`AnalysisContextItem.timestamp`",
        "`AnalysisContextBlock.timestamp`",
        "Optional[str]",
        "构造时校验",
        "date-only",
        "`block.status` 表示整块可用性",
        "`item.status` 表示字段级质量",
        "不实现 `item.status` 到 `block.status` 的自动聚合推导",
    ):
        assert token in section


def test_analysis_context_pack_doc_records_p1_redaction_contract() -> None:
    section = _section(_read_doc(), "P1 内部契约")

    for token in (
        "`AnalysisContextPack.to_safe_dict()`",
        "`redact_sensitive_mapping()`",
        "`api_key`",
        "`access_token`",
        "`authorization_header`",
        "`webhook_url`",
        "`license_key`",
        "[REDACTED]",
        "`data_api`",
        "不扫描普通字符串值",
        "不做 URL 正则脱敏",
    ):
        assert token in section


def test_analysis_context_pack_doc_keeps_later_phases_out_of_p1() -> None:
    section = _section(_read_doc(), "P1 内部契约")

    for token in (
        "不填充运行时数据",
        "不新增 fetcher",
        "不改变 Prompt",
        "不写入 history/task/report metadata",
        "不把完整 pack 暴露到 API、Web、Bot、Desktop 或通知",
        "P2 builder",
        "P3 runtime",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p2_builder_boundaries() -> None:
    section = _section(_read_doc(), "P2 Builder 契约")

    for token in (
        "`AnalysisContextBuilder`",
        "assembler",
        "pipeline 已 fetch",
        "zero-fetch",
        "`PipelineAnalysisArtifacts`",
        "`code`、`stock_name`、`market`",
        "`price_stale`",
        "`quote_stale`",
        "`intraday_realtime_overlay`",
        "`fetch_failed`",
        "P3 runtime",
        "不改变 Prompt",
        "不写入 history/task/report metadata",
    ):
        assert token in section


def test_analysis_context_pack_doc_defines_p3_runtime_consumption_boundaries() -> None:
    section = _section(_read_doc(), "P3 Runtime Consumption")

    for token in (
        "`StockAnalysisPipeline` 是 summary 的唯一生产者",
        "`PipelineAnalysisArtifacts` -> `AnalysisContextBuilder.build()`",
        "`format_analysis_context_pack_prompt_section()`",
        "`analysis_context_pack_summary`",
        "基础信息 -> #1386 `market_phase_context` 渲染区块 -> `analysis_context_pack_summary`",
        "`news.content`、`trend_result`、`chip`、`fundamental_context` 等原始 payload",
        "`AgentExecutor._build_user_message()`",
        "`AgentOrchestrator._build_context()`",
        "`ctx.meta[\"analysis_context_pack_summary\"]`",
        "禁止写入 `ctx.data`",
        "`BaseAgent._build_messages()`",
        "`_inject_cached_data()`",
        "`news` block 为 `missing` 是当前 P3 的预期状态",
        "`analysis_history.context_snapshot`",
        "`analysis_context_pack`",
        "`analysis_context_pack_summary`",
        "Agent 工具级 pack cache 复用",
        "历史 / 任务状态 / Web 可见性",
        "P4/P5",
    ):
        assert token in section

    assert "P3-min" not in section


def test_analysis_context_pack_doc_maps_existing_status_terms() -> None:
    section = _section(_read_doc(), "现有状态映射")

    for token in (
        "`degraded`",
        "`insufficient_data`",
        "`partial_failed`",
        "`data_missing`",
        "`price_stale`",
        "`data_quality=ok/partial/unavailable`",
        "不映射",
    ):
        assert token in section


def test_analysis_context_pack_doc_lists_source_anchors() -> None:
    section = _section(_read_doc(), "源码锚点")

    for path in (
        "src/core/pipeline.py",
        "src/storage.py",
        "src/analyzer.py",
        "src/agent/orchestrator.py",
        "src/agent/executor.py",
        "src/agent/tools/data_tools.py",
        "src/services/alert_worker.py",
        "src/services/portfolio_service.py",
        "src/services/backtest_service.py",
        "src/repositories/backtest_repo.py",
        "src/services/history_service.py",
        "api/v1/endpoints/history.py",
        "api/v1/endpoints/analysis.py",
        "api/v1/schemas/history.py",
        "api/v1/schemas/portfolio.py",
        "src/notification.py",
        "docs/alerts.md",
        "docs/notifications.md",
    ):
        assert path in section


def test_analysis_context_pack_doc_updates_indexes_and_changelog() -> None:
    index = (PROJECT_ROOT / "docs" / "INDEX.md").read_text(encoding="utf-8")
    index_en = (PROJECT_ROOT / "docs" / "INDEX_EN.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "[分析上下文包契约与运行态消费](analysis-context-pack.md)" in index
    assert "P1/P2 内部契约、P3 Prompt 摘要消费" in index
    assert (
        "[Analysis Context Pack Contract And Runtime Consumption](analysis-context-pack.md) "
        "<sub><sub>![P3 Badge](https://img.shields.io/badge/P3-yellow?style=flat)</sub></sub> "
        "(Chinese-only)"
    ) in index_en
    assert "P1/P2 internal contracts, P3 prompt-summary consumption" in index_en
    assert "[文档] 新增 AnalysisContextPack P0 上下文盘点" in changelog
    assert "[新功能] 新增 AnalysisContextPack P1 内部契约与脱敏序列化测试" in changelog
    assert "[新功能] 新增 AnalysisContextPack P2 builder" in changelog
    assert "[新功能] 普通分析与 Agent 运行时 Prompt 接入 AnalysisContextPack 低敏摘要" in changelog


def test_full_guides_clarify_pack_summary_does_not_replace_legacy_payload_channels() -> None:
    guide = (PROJECT_ROOT / "docs" / "full-guide.md").read_text(encoding="utf-8")
    guide_en = (PROJECT_ROOT / "docs" / "full-guide_EN.md").read_text(encoding="utf-8")

    assert "在这个新增的 pack 摘要区块中" in guide
    assert "不会通过该区块看到完整 `news.content`" in guide
    assert "既有 `news_context`、Agent pre-fetched JSON 和 `enhanced_context` 原始数据通道保持 P3 前行为" in guide

    assert "in this new pack-summary section" in guide_en
    assert "not full `news.content`" in guide_en
    assert "Existing `news_context`, Agent pre-fetched JSON, and `enhanced_context` raw-payload channels keep their pre-P3 behavior" in guide_en
