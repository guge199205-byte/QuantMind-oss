# AnalysisContextPack：P0 盘点、P1/P2 契约与 P3 Runtime Consumption

本页是 Issue #1389 的专题文档，用于记录当前 DSA 分析上下文的真实来源、消费路径、字段状态边界，以及 `AnalysisContextPack` 内部契约、builder 与运行态消费边界。P0 负责现状盘点和契约边界；P1 只新增内部 schema/envelope、block catalog、类型约定和脱敏序列化；P2 只从 pipeline 已有 artifacts 组装 pack；P3 只把低敏摘要接入普通分析和 Agent 初始 Prompt。

## 术语与边界

当前仓库里有多种名为 context / snapshot 的数据面，P0 必须先消歧，避免把现有运行时结构误写成未来 pack。

| 术语 | 当前含义 | 当前主要消费方 | P0 边界 |
| --- | --- | --- | --- |
| `storage.get_analysis_context()` | `src/storage.py` 中从数据库最近两天 OHLCV 生成的技术面简上下文，包含 `today`、`yesterday`、`volume_change_ratio`、`price_change_ratio`、`ma_status` 等。当前实现接收 `target_date`，但实际仍取最新两天数据。 | 普通分析主链路、Agent 工具 `get_analysis_context` | 记录为历史技术面输入来源，不把它直接等同于未来 pack。 |
| `enhanced_context` | 普通分析中由 `src/core/pipeline.py` 基于 DB 简上下文、实时行情、筹码、趋势、基本面和语言信息增强后的 prompt 上下文。 | `src/analyzer.py` prompt 渲染、`_build_context_snapshot()` | 记录当前 prompt 输入面；P0 不改变字段名或结构。 |
| `analysis_history.context_snapshot` | 分析完成后写入历史表的持久化快照。普通分析通常包含 `enhanced_context`、`news_content`、`realtime_quote_raw`、`chip_distribution_raw`；Agent 路径保存 `initial_context`。 | 历史详情、同步 analysis/status 响应、回测、部分基本面 fallback 展示 | 记录为持久化消费面；必须保留 `context_snapshot.enhanced_context.date` 兼容。 |
| Agent executor message context | `AgentExecutor._build_user_message()` 注入首轮用户消息的上下文，适用于 `AGENT_ARCH=single` 路径，目前包含股票代码、报告类型、输出语言、`realtime_quote`、`chip_distribution`、`news_context`。 | 单 Agent 首轮 LLM 消息 | 记录当前首轮可见字段；P0 不补 runtime 注入。 |
| Agent orchestrator `AgentContext` | `AgentOrchestrator._build_context()` 写入多 Agent 共享上下文，适用于 `AGENT_ARCH=multi` 路径，可预注入 `realtime_quote`、`daily_history`、`chip_distribution`、`trend_result`、`news_context`。 | Technical / Intel / Risk / Decision 多 Agent 链路 | 记录为 orchestrator 内部共享数据面；不预注入 `fundamental_context`，`trend_result` 是否存在取决于 caller 是否传入。 |

## P0 范围与非目标

P0 的目标是让后续 P1/P2/P3 可以基于真实仓库边界设计 `AnalysisContextPack`，而不是提前改造运行时。

- P0 覆盖普通分析、Agent、告警、持仓、回测、历史、通知七条路径的上下文盘点。
- P0 固定字段质量状态词；P1 已新增 `AnalysisContextPack` 内部 schema，但仍不新增 builder、不接入 runtime、不公开完整 pack。
- P0 不新增 builder，不新增配置项，不新增数据库字段，不改变 API、报告、历史或通知 payload。
- P0 不接入 runtime，不改 `src/` 分析、Agent、告警、持仓、回测或通知逻辑。
- P0 不 pack 化 `market_review`、`market_light` 或大盘红绿灯专题快照；这些只作为历史快照中的其他 `report_kind` / 专题消费边界记录。
- P0 不把 `fetch_failed` 加入字段质量状态词；`fetch_failed` 与 `not_supported` 的细分留到 P5 数据质量评分与模型提示阶段。
- P0 不在 README 扩写实现细节；本页作为专题文档，由 `docs/INDEX.md` / `docs/INDEX_EN.md` 入口发现。

## P1 内部契约

P1 落地 `src/schemas/analysis_context_pack.py`，只定义内部 schema/envelope，方便 P2 builder 和 P3 runtime 消费时复用同一结构。P1 不填充运行时数据、不新增 fetcher、不改变 Prompt、不写入 history/task/report metadata，也不把完整 pack 暴露到 API、Web、Bot、Desktop 或通知。

P1 schema 包含：

- `PACK_VERSION = "1.0"`，并通过 `AnalysisContextPack.pack_version` 标记契约版本。
- `ContextFieldStatus`：只允许 `available`、`missing`、`not_supported`、`fallback`、`stale`、`estimated`、`partial`；`fetch_failed` 仍留到 P5。
- `AnalysisSubject`：顶层身份槽，只包含 `code`、`stock_name`、`market`；`exchange`、`currency`、`industry` 留给后续扩展，P2 builder 不扩 P1 schema，也不重复新增 `identity` block。
- `AnalysisContextItem`：字段级输入项，包含 `status`、`value`、`source`、`timestamp`、`fallback_from`、`missing_reason`、`warnings`、`metadata`。
- `AnalysisContextBlock`：数据块级分组，包含 `status`、`items`、`source`、`timestamp`、`warnings`、`metadata`，其中 `items` 是 `Dict[str, AnalysisContextItem]`。
- `DataQuality`：P1 只保留 `warnings` 与 `metadata` 容器，不做评分、聚合计数或模型置信度限制。
- `AnalysisContextPack`：顶层 envelope，包含 `pack_version`、`subject`、`phase`、`blocks`、`data_quality`、`metadata`、`created_at`。

时间字段约定：

- `AnalysisContextPack.created_at` 使用 `datetime`，由 `model_dump(mode="json")` 输出 ISO 8601 字符串。
- `AnalysisContextItem.timestamp` 与 `AnalysisContextBlock.timestamp` 使用 `Optional[str]`，约定为 ISO 8601 datetime 字符串；P1 schema 在构造时校验该格式，date-only、自然语言时间或斜杠分隔日期会被拒绝；P2 builder 复用现有 artifact 时间戳时不做强制二次转换。

状态语义：

- `block.status` 表示整块可用性。
- `item.status` 表示字段级质量。
- P1 不实现 `item.status` 到 `block.status` 的自动聚合推导。

P1 Block Catalog：

| block key | P1 语义 | P1 边界 |
| --- | --- | --- |
| `quote` | 实时行情和报价相关输入 | 只定义可表达位置，不抓取或填充数据。 |
| `daily_bars` | 完整日线窗口和最近完整日线日期 | P1 不判断 partial bar。 |
| `technical` | 技术指标、量价结构和形态 | P1 不生成指标。 |
| `fundamentals` | 估值、成长、盈利、财报和股东回报 | P1 不新增基本面 fetcher。 |
| `news` | 新闻、公告、舆情和催化事件输入 | P1 不改变新闻搜索。 |
| `portfolio` | 是否持仓、账户摘要、成本、数量、仓位和 stale 摘要 | P1 不纳入交易流水、现金流水或完整账户隐私数据。 |
| `chip` / `capital_flow` | 筹码、资金流和主力行为 | 后续扩展键，P1 只允许契约表达。 |
| `events` / `market_context` | 风险事件、市场宽度、指数、板块和热点环境 | 后续扩展键，不把 `market_review` / `market_light` 作为首版单股 pack。 |

`phase` 字段只接收 #1386 `MarketPhaseContext.to_dict()` 产物，保持 `Dict[str, Any]`，不重新定义 phase enum 或 phase 子模型。

脱敏边界：

- `AnalysisContextPack.to_safe_dict()` 先执行 `model_dump(mode="json")`，再调用 `redact_sensitive_mapping()`。
- `redact_sensitive_mapping()` 只做 dict/list 的 key-based 递归脱敏，命中 `api_key`、`access_token`、`refresh_token`、`authorization_header`、`webhook_url`、`password`、`cookie`、`secret`、`token`、`sendkey`、`license_key` 等敏感键或短语时把值替换为 `[REDACTED]`。
- P1 不扫描普通字符串值，不做 URL 正则脱敏，不把 `data_api` 或裸 `api` / `key` 当作敏感命中，避免把本契约扩展成通用 secrets engine。

## P2 Builder 契约

P2 新增 `AnalysisContextBuilder`，但首版只做 assembler：从普通分析 pipeline 已经拿到的 artifacts 组装内部 `AnalysisContextPack`。Issue 验收项里的“复用现有数据源”在本 slice 中解释为复用 pipeline 已 fetch 的 `realtime_quote`、`base_context`、`enhanced_context`、`trend_result`、`chip_data`、`fundamental_context`、`news_context` 等 artifacts；builder 本身 zero-fetch，不调用 DB、fetcher、SearchService、Agent 工具或具体 provider。

P2 输入契约使用 `PipelineAnalysisArtifacts`：`code`、`stock_name`、`market`、`phase`、`base_context`、`enhanced_context`、`realtime_quote`、`trend_result`、`chip_data`、`fundamental_context`、`news_context`、`news_result_count`、`metadata`。单股 `build()` 与批量 `build_batch()` 复用同一结构，避免 P3 runtime 接入时再次改签名。

P2 block 组装边界：

- `subject` 仍只写 `code`、`stock_name`、`market` 三字段，不扩 `AnalysisSubject`。
- `phase` 只接收传入的 `MarketPhaseContext.to_dict()` 产物，不从 `enhanced_context` 反推。
- `quote` 从 `realtime_quote` 组装；缺失为 `missing`；`source=fallback` 映射为 `fallback`；`fallback_from` 只在 artifact/metadata 显式提供时填写，否则只记录稳定 warning code，不伪造 provider 链。
- `quote` stale 只透传 `price_stale`、`quote_stale`、`quote_stale_seconds` 等显式 marker；builder 不推断新鲜度。
- `daily_bars` 只表达完整日线窗口，优先读 `base_context.today`、`base_context.yesterday`、`base_context.date`、`base_context.data_missing`；date-only 放入 `value` 或 `metadata`，不写入 `timestamp`。
- `enhanced_context.today.data_source` 为 `realtime:*` 时，只影响 `technical`：block 标 `partial`，相关 item 标 `estimated`，warning 使用 `intraday_realtime_overlay`。
- `technical` 优先复用 `trend_result.to_dict()`；无 trend artifact 时为 `missing`。
- `chip` 复用 `chip_data.to_dict()`；无 chip artifact 默认 `missing`，只有输入 metadata/artifact 明确 not_supported 时才标 `not_supported`。
- `fundamentals` 只读 `fundamental_context` 参数；`ok` 映射为 `available`，`not_supported` 映射为 `not_supported`，`partial` 映射为 `partial`，`failed` 映射为 `missing` + 稳定 reason code；不写入 `errors[]` 原文。
- `news` 非空白字符串为 `available`，空白或缺失为 `missing`；`news_result_count` 写入 pack metadata。

P2 不组装 `portfolio`、`events`、`market_context`，也不把 `capital_flow` 拆成独立 block；首版只把它保留在 fundamentals 的 coverage/source chain metadata 中。P2 也不改变 Prompt、不让普通分析或 Agent runtime 消费 pack、不写入 history/task/report metadata、不暴露完整 pack 到 API/Web/Bot/Desktop/通知，不做 P5 data-quality scoring、`fetch_failed` 细分或模型置信度限制。

## P3 Runtime Consumption

P3 在 P2 `AnalysisContextBuilder` 之后接入运行态消费，但消费面限定为低敏 `analysis_context_pack_summary`。`StockAnalysisPipeline` 是 summary 的唯一生产者：在普通分析路径和 Agent 路径内完成 `PipelineAnalysisArtifacts` -> `AnalysisContextBuilder.build()` -> `format_analysis_context_pack_prompt_section()`，下游 analyzer、single-agent、multi-agent 只接收 summary 字符串，不自行构造完整 pack，也不读取 `AnalysisContextPack.to_safe_dict()` 的 block item 原始值。

普通分析 Prompt 的顺序固定为：基础信息 -> #1386 `market_phase_context` 渲染区块 -> `analysis_context_pack_summary` -> 技术面、实时行情、新闻等既有区块。`analysis_context_pack_summary` 只包含 subject、`pack_version`、block `status` / `source` / `warnings` / `missing_reason`、`metadata.news_result_count` 和 `data_quality.warnings`，不得输出 `news.content`、`trend_result`、`chip`、`fundamental_context` 等原始 payload。

Agent 路径同样只传 summary。`AgentExecutor._build_user_message()` 在 market phase 段之后、pre-fetched JSON 之前插入 summary；`AgentOrchestrator._build_context()` 只把 summary 放入 `ctx.meta["analysis_context_pack_summary"]`，禁止写入 `ctx.data`；`BaseAgent._build_messages()` 在 market phase user message 之后、`_inject_cached_data()` 之前插入 summary。Agent 首轮没有复用普通分析新闻检索，`news` block 为 `missing` 是当前 P3 的预期状态。

P3 仍不持久化完整 pack，不新增 API/Web/Bot/Desktop 字段，不改变报告 JSON schema，不把 summary 写入 `analysis_history.context_snapshot`、task status 或 report metadata；history snapshot 和 diagnostic snapshot 会剥离 `market_phase_context`、`analysis_context_pack`、`analysis_context_pack_summary` 等 runtime prompt key。Agent 工具级 pack cache 复用、历史 / 任务状态 / Web 可见性、通知展示和数据质量评分留给 P4/P5 后续阶段。

## 字段质量状态

未来 pack 的字段质量状态在 P0 只固定下列七词。它们描述字段或数据块的质量，不描述业务流程是否成功。

| 状态 | 含义 | 示例边界 |
| --- | --- | --- |
| `available` | 字段存在，来源和时间戳可解释，当前路径可正常使用。 | 实时行情返回价格和来源；历史 K 线窗口满足计算需求。 |
| `missing` | 当前路径需要该字段，但实际未取到或为空。 | DB 无最近日线，普通分析进入 `data_missing` 结果。 |
| `not_supported` | 当前市场、数据源或路径不支持该字段，不应误报为错误。 | 某些市场无筹码分布或资金流。 |
| `fallback` | 首选来源不可用，使用了备用来源或旧路径。 | 持仓价格从实时行情 fallback 到历史收盘价。 |
| `stale` | 字段存在，但时间新鲜度不足。 | 持仓估值中的 `price_stale` / `fx_stale`。 |
| `estimated` | 字段是估算值，不应当作完整事实。 | 盘中用实时价补今日 bar 后生成技术估计。 |
| `partial` | 数据块部分可用、部分缺失。 | 大盘红绿灯 `data_quality=partial` 或工具返回 `partial_cache`。 |

## 现有状态映射

当前仓库已有不少状态词。P0 只建立映射或不映射关系，避免后续把业务结果状态混入字段质量枚举。

| 现有词或字段 | 当前位置 | 建议关系 | 说明 |
| --- | --- | --- | --- |
| `data_missing` | 普通分析缺历史数据结果 | 可映射到 `missing` | 这是核心输入缺失，不是业务成功状态。 |
| `cache_hit` / `partial_cache` | Agent 历史数据工具 | `partial_cache` 可映射到 `partial` | `cache_hit` 是来源/缓存元数据，不是质量状态。 |
| `source` / `data_source` / `realtime_source` | 数据源、告警、上下文快照 | 不映射 | 这些是来源元数据，应与字段质量状态并列保存。 |
| `price_source=missing` | 持仓快照 | 可映射到 `missing` | 表示估值价格不可用。 |
| `price_stale` / `fx_stale` | 持仓快照 | 可映射到 `stale` | 保留原字段作为业务元数据。 |
| `triggered` / `skipped` / `degraded` / `failed` | 告警评估与记录 | 不映射 | 这是规则评估或记录结果，不是字段级质量状态。 |
| `insufficient_data` / `completed` / `error` | 回测服务 | 不映射 | 这是回测执行状态；可在 pack 摘要中解释触发原因。 |
| `sent` / `no_channel` / `partial_failed` / `all_failed` | 通知发送 | 不映射 | 这是通知投递结果，不能反推分析输入质量。 |
| `data_quality=ok/partial/unavailable` | 大盘红绿灯 | `partial` 可映射，`unavailable` 视字段场景映射到 `missing` 或 `not_supported` | P0 不把大盘红绿灯纳入首版单股 pack。 |
| `fetch_failed` | 未来数据质量细分 | P0 不扩展 | P5 再区分 `not_supported` 与 `fetch_failed`。 |

## 七路径盘点

### 普通分析

普通分析主链路在 `src/core/pipeline.py` 中组装输入：先读取 `storage.get_analysis_context()`，再按可用性补充实时行情、筹码、趋势分析、新闻、基本面和报告语言，最后交给 `src/analyzer.py` 渲染 prompt。当前重复点主要是实时字段同时存在于 `enhanced_context.realtime`、`realtime_quote_raw` 和报告 meta；命名上存在 `source`、`data_source`、`realtime_source` 等多种来源字段。

首版 pack 可从普通分析路径抽取单股核心身份、行情、日线、技术、新闻、基本面和数据质量摘要；P0 不改变 `_enhance_context()`、`_build_context_snapshot()` 或 analyzer prompt。

### Agent

Agent 有三层需要分开记录的数据面。`src/core/pipeline.py` 的 Agent 路径会构造 `initial_context`，固定包含 `fundamental_context`，并在可用时加入 `trend_result`，最终作为 Agent 路径的 `context_snapshot` 持久化。`AgentExecutor._build_user_message()` 只适用于 `AGENT_ARCH=single`，首轮消息只显式注入 `realtime_quote`、`chip_distribution`、`news_context` 等已取上下文，不显式注入 `fundamental_context` 或 `trend_result`。`AgentOrchestrator._build_context()` 适用于 `AGENT_ARCH=multi`，可预注入 `realtime_quote`、`daily_history`、`chip_distribution`、`trend_result`、`news_context`，这些进入 `AgentContext` 的字段会作为 pre-fetched data 注入 stage agent 消息；但 orchestrator 不预注入 `fundamental_context`。`trend_result` 不是天然存在，取决于 caller 是否传入。

Agent 工具还会独立调用 `get_realtime_quote`、`get_daily_history`、`get_chip_distribution`、`get_analysis_context`、`get_stock_info` 等工具，容易与普通分析前置获取产生重复请求。P0 只记录这些重复和命名差异，P3 再决定如何让 Agent 复用 pack。

### 告警

告警链路在 `src/services/alert_worker.py` 中评估规则、记录触发历史并分发通知，具体字段语义见 [实时告警中心](alerts.md)。告警状态如 `triggered`、`skipped`、`degraded`、`failed` 是规则评估或记录状态，不能直接写入字段质量枚举。

首版 pack 不把告警规则评估作为输入数据块；告警后续只消费 pack 的字段质量摘要，例如核心行情是否 fallback、是否 stale、是否 partial。

### 持仓

持仓快照在 `src/services/portfolio_service.py` 中聚合账户、仓位、成本、价格、汇率和风险输入，API 输出结构在 `api/v1/schemas/portfolio.py`。当前已有 `price_source`、`price_provider`、`price_date`、`price_stale`、`price_available`、`fx_stale` 等字段。

首版 pack 可记录“是否持仓、账户摘要、成本、数量、仓位、浮盈浮亏、价格/汇率 stale 摘要”，但不纳入交易流水、现金流水、公司行动或完整账户隐私数据。

### 回测

回测服务在 `src/services/backtest_service.py` 和 `src/repositories/backtest_repo.py` 中消费历史分析记录与日线数据。现有 `parse_analysis_date_from_snapshot()` 依赖 `analysis_history.context_snapshot.enhanced_context.date` 解析分析日期。

P0 必须把 `enhanced_context.date` 标为兼容边界。后续 pack 可以新增更清晰的日期字段，但不能无迁移地删除或改名当前历史快照中的日期位置。

### 历史

历史详情在 `src/services/history_service.py`、`api/v1/endpoints/history.py`、`api/v1/schemas/history.py` 中返回 `raw_result`、`news_content`、`context_snapshot` 等字段。同步 analysis/status 响应也会在 `api/v1/endpoints/analysis.py` 中读取 `context_snapshot.enhanced_context`、`realtime_quote_raw` 和基本面 fallback。

P0 只记录历史消费面。完整 pack 不应默认公开到历史详情或公共 API；后续 P4 如需展示，应优先暴露摘要、来源和降级说明。

### 通知

通知链路在 `src/notification.py` 中消费 `AnalysisResult`、dashboard、market snapshot、data_sources 等输出，并记录 `sent`、`no_channel`、`partial_failed`、`all_failed` 等投递状态；渠道配置与边界见 [通知能力基线](notifications.md)。

通知不是事实数据层，不能把投递失败误写成输入质量失败。后续只应在必要时消费 pack 摘要，例如“实时行情已降级”“基本面缺失”“新闻源不足”。

## 源码锚点

| 域 | 锚点 |
| --- | --- |
| 普通分析 | `src/core/pipeline.py`, `src/storage.py`, `src/analyzer.py` |
| Agent | `src/agent/orchestrator.py`, `src/agent/executor.py`, `src/agent/tools/data_tools.py` |
| 告警 | `src/services/alert_worker.py`, `docs/alerts.md` |
| 持仓 | `src/services/portfolio_service.py`, `api/v1/schemas/portfolio.py` |
| 回测 | `src/services/backtest_service.py`, `src/repositories/backtest_repo.py` |
| 历史 | `src/services/history_service.py`, `api/v1/endpoints/history.py`, `api/v1/endpoints/analysis.py`, `api/v1/schemas/history.py` |
| 通知 | `src/notification.py`, `docs/notifications.md` |

## 兼容与安全边界

- `analysis_history.context_snapshot.enhanced_context.date` 是当前回测日期解析兼容点，P1/P2 不能在没有迁移的情况下破坏。
- 完整 pack 不默认公开到历史、API、Web 或通知；公共面优先展示摘要、来源、fallback、stale、missing count 等低敏信息。
- pack、日志、历史快照和 API 响应不得记录 API key、token、cookie、完整 webhook URL、邮箱密码、私有环境变量或其他密钥。
- `source`、`timestamp`、`fallback`、`stale`、`partial` 等质量元数据只用于解释输入限制，不用于阻断分析；除非现有核心路径本来就是 fail-fast。
- #1386 的盘前 / 盘中 phase 感知是后续 `phase` / `data_quality` 字段的重要背景；P0 只记录关系，不接入 runtime。
