# AI Strategy Service

AI 策略服务是 QuantMind 平台的核心智能模块，负责将用户的自然语言需求转化为结构化的交易指令或选股 SQL。该服务支持 **Qwen (千问)** 与 **DeepSeek** 两类大模型，并结合 DashScope 向量模型实现精准语义解析与自动化选股链路。

## 📦 模块架构 (2026-02 重构)

代码按职责分层，遵循 5 步策略生成流程组织：

```
backend/ai_strategy/
├── api/
│   ├── v1/
│   │   ├── wizard.py          # 策略向导：选股解析 / 文本解析
│   │   ├── validation.py      # Qlib 校验 / AI 修复
│   │   ├── storage.py         # 云端保存 / 股票池文件
│   │   ├── generation.py      # Qlib 生成 / 异步任务 / 远程策略
│   │   ├── routes.py          # 核心策略路由：CRUD / 生成 / 分析 / 执行 / 导入导出
│   │   ├── support.py         # 模板 / 校验 / 监控 / 文件管理
│   │   └── pool_files.py      # 旧版股票池文件兼容路由
│   └── schemas/               # Pydantic 请求/响应模型
│       ├── stock_pool.py      # 股票池相关
│       ├── strategy_params.py # 策略参数（TopK/买卖规则/风控）
│       ├── style.py           # 风格配置
│       ├── generation.py      # LLM 生成 / Qlib 生成
│       ├── backtest.py        # 回测
│       ├── text_parse.py      # 文本解析
│       ├── market.py          # 市场状态
│       └── remote.py          # 远程策略
├── steps/                     # 5步业务逻辑
│   ├── step1_stock_selection.py  # 条件解析 → DSL
│   ├── step2_pool_confirmation.py # 股票池查询
│   ├── step3_strategy_params.py   # 参数验证
│   ├── step4_style_config.py      # 风格预设
│   └── step5_generation.py        # LLM 策略生成
├── llm/                       # LLM 提供者统一接口
│   ├── base.py                # BaseLLMProvider 抽象基类
│   ├── qwen.py                # Qwen 同步 + 异步
│   ├── deepseek.py            # DeepSeek 同步 + 异步
│   ├── prompt_builder.py      # 提示模板
│   └── code_cleaner.py        # 代码清理
├── storage/                   # 存储层
│   ├── cloud.py               # COS 云端存储
│   └── database.py            # 数据库 CRUD
└── generators/                # Qlib 策略代码生成器
    └── qlib_strategy_generator.py
```

## 📌 V1 路由拆分说明

为了降低 `api/v1` 单文件复杂度，当前路由按职责拆分为：

- `routes.py`：策略核心路由，保留生成、CRUD、分析、执行、导入导出等主流程
- `support.py`：模板匹配、验证、健康检查、性能统计、文件管理
- `pool_files.py`：`/legacy/strategy/*` 股票池文件兼容入口
- `wizard.py`：选股条件解析、文本解析
- `validation.py`：Qlib 校验与 AI 修复
- `storage.py`：云端保存与股票池文件管理
- `generation.py`：Qlib 生成、异步任务与远程策略查询

路由前缀与对外 API 路径保持不变，拆分仅影响内部组织方式。

## 🔒 安全加固 (2026-02-16)

本次更新修复了多个严重安全问题：

1. ✅ **修复数据库初始化执行方式**: 统一使用 PostgreSQL SQL 执行链路，避免驱动差异导致的执行错误
2. ✅ **SQL注入防护**: 新增 `sql_validator` 模块，实现表名白名单、危险操作拦截、参数化查询
3. ✅ **异步/同步改进**: 使用 `asyncio.to_thread` 包装同步I/O，避免阻塞事件循环
4. ✅ **移除硬编码密码**: 数据库配置不再包含默认密码，启动时强制验证
5. ✅ **连接管理加固**: 添加 try-finally 确保连接正确关闭，防止泄漏

详见: [架构分析报告](/.copilot/session-state/.../files/ai_strategy_architecture_analysis.md)

## 🔄 最近变更 (2026-02-18)

1. `app_factory` 注册链路修复：统一使用 `create_app()` 内部创建的 `app` 对象完成路由、中间件与生命周期注册，避免变量混用导致的挂载异常。
1. `wizard` 路由启动导入修复：`support.py` 依赖的 `get_file_stats` 现由 `storage/database.py` 提供兼容实现，避免 `engine/main.py` 在加载 AI Strategy 路由时直接跳过 `parse-text` / `parse-conditions` / `query-pool`。
2. `query-pool` 鉴权收紧：`step2_pool_confirmation._require_user_id` 不再回退 `dev_user_001`，缺少 `request.state.user.user_id` 或 `tenant_id` 时直接拒绝请求（401/403）。
3. 多租户边界强化：`/api/v1/strategy/query-pool` 现要求网关/鉴权中间件先注入完整用户上下文，再进入业务查询。
4. 路由入口收敛：`wizard` 路由改为由 `app_factory` 统一挂载；`routes.py` 中与 `wizard` 冲突的 `/strategy/save-pool-file`、`/strategy/get-active-pool-file` 已迁移为 `/legacy/strategy/*` 兼容入口。
5. 网关上下文注入：新增中间件读取 `X-User-Id`、`X-Tenant-Id`、`X-Trace-Id` 并写入 `request.state`，用于统一多租户鉴权与链路追踪。
6. `query-pool` 错误语义修正：鉴权失败（401/403）不再包装为 500，直接透传给调用方。
7. 生产默认关闭 legacy 路由：`/api/v1/legacy/strategy/*` 默认禁用，需显式设置 `AI_STRATEGY_ENABLE_LEGACY_ROUTES=true` 才启用。
8. LLM 弹性调度上线：策略生成链路启用“主备 + 熔断 + 重试 + 限流”，默认主模型失败时自动回退到备模型。
9. OpenAPI 噪音收敛：`routes.py` 中与统一策略入口重复的 `GET/PUT/DELETE /strategies/{strategy_id}` 标记为 `include_in_schema=False`，避免与 `qlib_app/api/user_strategies.py` 的 operationId 冲突告警；运行时兼容路由仍可访问。
10. `query-pool` 字段兼容增强：快照查询改为运行时兼容 `symbol/code`、`name/stock_name`、`amount/turnover`、`idx_hs300/is_hs300/is_csi300`、`idx_zz1000/is_csi1000`，避免字段漂移导致 500。
11. `query-pool` 错误语义优化：遇到数据库字段缺失时返回 `422` 友好错误，不再笼统包装为 500。
12. `parse-conditions` 市值口径统一：`market_cap` 统一按前端“亿”输入换算为数据库 `total_mv` 口径（默认亿元，可由 `AI_STRATEGY_TOTAL_MV_PER_YI` 覆盖兼容旧库），与 `parse-text` 语义对齐。
13. `parse-text` 选股纠偏：修复“成分股”被误识别为行业词导致 HS300/CSI1000 结果为 0；金融主题映射补充 `金融信息服务`，贴合当前 `industry` 字段真实取值。

## 🔄 最近变更 (2026-03-09)
1. `StrategyService._build_strategy_prompt` 已对齐 QuantMind Qlib 策略开发规范 V1.1：
   - 增加 `STRATEGY_CONFIG/get_strategy_config` 入口约束；
   - 增加 `__init__ kwargs.pop()` 与 `reset(*args, **kwargs)` 兼容约束；
   - 明确 `level_infra/common_infra/trade_exchange` 参数差异回退要求；
   - 继续保持 JSON 输出结构（`strategy_name/rationale/python_code/...`）不变，兼容现有响应解析逻辑。
2. `generate-qlib` 调仓参数兼容增强：`qlib_params` 现优先支持 `rebalance_days`（1/3/5 个交易日），并向后兼容 `rebalance_period`（daily/weekly/monthly）口径。

## 🔄 最近变更 (2026-04-08)
1. `api/v1/routes.py` 已继续拆分出 `support.py` 与 `pool_files.py`，避免模板/验证/兼容路由与主策略路由耦合。
2. `api/v1/wizard.py` 已继续收敛为选股解析/文本解析主链路，Qlib 验证、云端保存、生成任务与远程策略已拆到 `validation.py`、`storage.py`、`generation.py`。

## 🔐 安全与一致性更新 (2026-02-20)
1. `save-to-cloud` 身份绑定强化：服务端改为使用鉴权上下文中的 `user_id` 执行保存；若请求体 `user_id` 与鉴权身份不一致，返回 `403`。
2. 文档协议对齐：补充 `generate/stream` 的 `error` / `[DONE]` 事件说明，以及 `generate`/`parse-text` 的扩展字段说明（`hints`、`warnings`、`version`）。

## ⚙️ 异步执行收敛 (2026-02-25)
1. `strategy-backtest-loop` 路由迁移为 Celery 入队执行，状态/结果统一通过任务系统查询，不再使用进程内 `BackgroundTasks` 内存态任务表。
2. `ai_strategy_app` 的性能监控与自动故障切换改为被动模式：不再创建服务内后台线程或 `create_task` 监控循环。
3. `strategy-backtest-loop` 接口身份统一来自 `request.state.user`，并按 `user_id + tenant_id` 持久化任务归属，杜绝跨用户查询/取消任务。
4. 配置兼容更新：`ai_strategy_config.py` 已切到 `SettingsConfigDict`，避免 Pydantic V2 对 class-based settings config 的弃用告警。

## 核心架构：双引擎解析链路

系统采用"向量感知 + Schema检索 + 模型生成"的三阶段处理流程：

1.  **Stage 1: 向量语义对齐 (Vector Routing)**
    *   使用 DashScope `text-embedding-v4` 模型将用户输入向量化。
    *   通过与预设的"策略原型"（如价值投资、成长发现、技术解析等）进行余弦相似度匹配，精准定位用户的投资意图。
2.  **Stage 2: Schema检索增强 (Schema RAG)**
    *   基于 `text-embedding-v4` 检索字段/表信息，输出候选字段与目标表。
    *   支持 `stock_selection`（近30天快速筛选）与 `stock_daily`（全量历史）。
3.  **Stage 3: 精准指令生成 (NL-to-SQL)**
    *   基于语义 + Schema 候选字段，驱动 Qwen 生成 SQL。
    *   通过白名单字段与 SQL 校验约束，避免错表/错字段。

## LLM提供商

**本服务支持 Qwen 与 DeepSeek 两类大模型**，可通过环境变量选择：

- **策略生成**: Qwen `qwen-max` 或 DeepSeek `deepseek-chat`
- **意图解析**: Qwen / DeepSeek
- **SQL生成**: Qwen / DeepSeek
- **向量化**: DashScope `text-embedding-v4`

## 主要功能

*   **智能语义解析**：理解复杂口语化需求（如"帮我找低市盈率的长线白马股"）。
*   **因子自动映射**：自动对应 20+ 个核心因子指标（ROE, PE, MACD, KDJ, 换手率等）。
*   **交易规则配置**：
    *   **本地极速模式**：前端集成 Regex 引擎，支持即时识别并将自然语言描述转化为结构化交易规则。
    *   **参数自动带入**：自动提取涨幅阈值、均线天数及止损/止盈比例。
*   **单位自动换算**：支持自然语言中的单位（如"100亿"自动换算为数据库 `total_mv` 单位，默认万元）。
*   **端到端选股执行**：直接从数据库检索匹配股票，支持前端结果勾选与二次过滤。
*   **自动注册到统一策略接口**：AI 生成的策略会自动同步到 `quantmind-engine` 的 `/api/v1/strategies` 入口（默认 8001，经网关转发），实现统一策略管理和回测入口。可通过 `STRATEGY_SYNC_ENABLED=false` 关闭。

## 环境变量配置

⚠️ **必需配置** (2026-02-16 更新)：以下配置项启动时会强制验证，缺失将无法启动

在项目根目录 `.env` 文件中配置：

```env
# 选择模型提供商（qwen 或 deepseek）
LLM_PROVIDER=qwen

# 仅在迁移窗口需要时启用 legacy 路由（生产建议保持 false）
AI_STRATEGY_ENABLE_LEGACY_ROUTES=false

# LLM 弹性调度（第二周）
LLM_FALLBACK_PROVIDERS=deepseek
LLM_PROVIDER_MAX_RETRIES=2
LLM_RETRY_BASE_SECONDS=0.5
LLM_CIRCUIT_FAILURE_THRESHOLD=3
LLM_CIRCUIT_OPEN_SECONDS=30
LLM_RATE_LIMIT_RPM=120
LLM_MAX_CONCURRENCY=4

# 禁用历史 mock 回测/执行接口（推荐保持 true）
ENGINE_DISABLE_MOCK=true

# 关闭后 save-to-cloud 仅上传 COS，不再同步 strategy-service
STRATEGY_SYNC_ENABLED=true

# Qwen (千问) 配置 - 必需
QWEN_API_KEY=your_qwen_api_key_here  # ⚠️ 必需
QWEN_MODEL=qwen-max
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MAX_TOKENS=4000
QWEN_TEMPERATURE=0.3

# DeepSeek 配置（当 LLM_PROVIDER=deepseek）
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_URL=https://api.deepseek.com
DEEPSEEK_BASE_URL=https://api.deepseek.com  # 兼容旧配置，优先使用 DEEPSEEK_API_URL

# 阿里云 DashScope 配置 - 向量化引擎
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_EMBEDDING_TIMEOUT=60

# 数据库配置 - 必需（统一优先使用 DATABASE_URL）
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database  # ⚠️ 必需，请替换为实际连接
# 兼容旧变量（可选，不推荐）
AI_STRATEGY_DB_URL=postgresql+asyncpg://user:password@host:5432/database

# 启动预热改为强制执行：服务启动时会预热向量解析器和字段检索，失败将直接阻断启动
AI_STRATEGY_WARMUP=true
```

**注意**: 
- `QWEN_API_KEY` 和 `DASHSCOPE_API_KEY` 通常使用同一个阿里云 API Key
- 数据库密码禁止使用默认值（如 `postgres:password`），启动时会检测并拒绝

## 数据库架构

服务主要操作以下数据表：
*   `stock_selection`: 滚动更新的选股因子表（近30天，快速筛选）。
*   `stock_daily`: 日线全量历史行情与估值表（长期筛选/风控指标）。
*   `stock_basic`: 存储股票基础资料（行业、上市日期等）。

## 开发与运行

**Docker 说明**：镜像基于 `python:3.10-slim`，以满足 `pyqlib` 依赖要求。
**模块内构建**：`backend/ai_strategy` 目录内可直接 `docker build`，所需的 `requirements/` 与 `shared/` 已在本模块内提供一份副本，需与仓库根目录保持同步。
**pyqlib 说明**：依赖已锁定为 `pyqlib==0.9.7`，并仅在 `x86_64/AMD64` 平台安装；默认构建会跳过 `pyqlib`（`SKIP_PYQLIB=1`）以兼容部分 Linux/ARM 环境，如需安装请使用 x86_64 基础镜像并传 `--build-arg SKIP_PYQLIB=0`。
**依赖说明**：`prometheus-client` 版本跟随统一 requirements（>=0.20.0），避免与基础依赖冲突。
**查询容错**：`query-pool` 对空值字段做了安全处理，避免因缺失字段导致解析失败。默认返回匹配的全部结果，不再强制 `limit 500`。
**预览容错**：`preview-pool-file` 对 `market_cap/pe/pb/roe/close/amount/volume` 做有限值清洗（`NaN/Inf -> 0`），避免 JSON 序列化触发 `Out of range float values are not JSON compliant` 导致接口 `500`。
**结果上限**：`query-pool` 在 SQL 分支默认上限为 `10000`（环境变量 `AI_STRATEGY_QUERY_POOL_LIMIT` 可调，最大 `50000`），避免历史 `1000` 条硬截断导致全市场场景结果不完整。
**标准话术**：市值字段统一口径为“接口返回 `market_cap` 使用亿元，数据库底层 `total_mv` 默认按亿元存储；若仍使用旧库单位，可通过 `AI_STRATEGY_TOTAL_MV_PER_YI` 配置兼容”；本地文本解析支持“亿 -> total_mv”换算，并支持“小市值/小盘股”默认阈值 `<=500亿`；“金融股/金融板块/金融行业”统一解析为 `银行`、`保险`、`证券` 三个行业。
**宽松查询策略**：本地规则解析新增“比较词同义归一 + 近似值区间化 + 行业词兜底”，支持“以上/以下/不超过/不少于/约XX左右/XX板块(股)”等自然表达，优先在本地命中并回传宽松策略提示。
**行业主题映射增强**：新增“主题词 -> `industry` 字段门类名”映射（如科技/军工/新能源/医药/消费/地产/基建/交通运输/公用事业/传媒等），自定义行业条件默认走 `industry` 宽松匹配。
**启动预热**：服务启动时会预热向量解析与字段检索（会调用 DashScope embeddings），首次启动可能耗时几十秒，属于正常现象。
**COS 读取稳定性**：`generate-qlib` 读取股票池文件改为线程化非阻塞执行，并增加 `COS_READ_TIMEOUT_SECONDS`（默认 30s）超时保护，避免同步 I/O 阻塞事件循环导致整服务请求超时。
**股票池保存一致性**：`save-pool-file` 现强制“COS + DB 双写一致”，若 `stock_pool_files` 落库失败将返回失败并回滚已上传对象，避免出现前端提示成功但“我的股票池”不可复用的假成功。
**股票池预览简称回填**：股票池 `txt` 文件仅保存 QLib 代码列表，`preview-pool-file` 预览接口需额外查询 `stock_name` 补齐简称，避免第二步复用历史股票池时名称列为空。

1.  **部署服务** (默认端口 8008，统一入口):
    ```bash
    python -m backend.ai_strategy.main
    ```
2.  **主要路由**:
    
    **Phase 1 - 策略生成与选股**:
    *   `POST /api/v1/strategy/generate`: 生成策略代码
    *   `POST /api/v1/stocks/select`: 智能选股
    *   `POST /api/v1/strategy/parse-text`: 解析文本需求
    *   `POST /api/v1/strategy/query-pool`: 执行SQL并返回股票池
    
**Phase 2 - 市场分析与云端存储** (NEW):
    *   `GET /api/v1/strategy/market-state`: 市场状态检测（实时沪深300数据）
    *   `POST /api/v1/strategy/validate-qlib`: Qlib策略代码验证（支持 `mode=syntax_only` 仅语法检查）
    *   `POST /api/v1/strategy/repair-qlib`: AI 修复 Qlib 策略代码（主要用于语法/结构问题；每轮修复后自动语法校验，最多 `max_rounds` 轮）
    *   `POST /api/v1/strategy/save-to-cloud`: 策略保存到云端（腾讯云COS）
    *   `POST /api/v1/strategy/save-pool-file`: 保存股票池到 COS（推荐 `txt`，内容为 QLib instruments：`SZ000001`）
    *   `POST /api/v1/strategy/get-active-pool-file`: 获取用户当前活跃股票池文件
    *   `POST /api/v1/strategy/list-pool-files`: 列出用户历史股票池（用于第二步弹窗复用/管理）
    *   `POST /api/v1/strategy/preview-pool-file`: 预览某个历史股票池（返回列表+summary）
    *   `POST /api/v1/strategy/delete-pool-file`: 删除股票池文件（支持按 `user_id + file_key` 删除 COS 对象并同步清理 `stock_pool_files` 元数据）
    *   `POST /api/v1/strategy/generate-qlib`: 基于 `pool_file_key` 与参数生成 Qlib 策略
    *   `POST /api/v1/strategy/generate-qlib/async`: 提交 Qlib 生成异步任务（返回 `task_id`）
    *   `GET /api/v1/strategy/generate-qlib/tasks/{task_id}`: 查询 Qlib 生成任务状态与结果

## 实盘代码生成约定（generate-qlib）
为降低提示词噪声并保持职责边界清晰：
- 智能策略在调用大模型生成策略代码时，会**过滤掉回测相关参数**（例如回测起止时间、基准、回测账户等），并保留仓位/风格/风险参数用于生成实盘逻辑。
- 大模型输出应面向**实盘可用**的策略逻辑与风控/调仓配置（如最大回撤、最大持仓数、调仓频率、动态仓位等）。
- 前端传入的 `risk_config` 会在后端统一做 `camelCase -> snake_case` 归一化（含 `stopLoss/takeProfit/commission/stampDuty/transferFee/slippage`）后透传至提示词，避免字段名不一致导致参数丢失。
- 回测模块会在运行时注入回测时段与基准等回测参数，策略生成阶段不应硬编码回测专用配置。
- 股票池地址约定：`generate-qlib` 会同时注入 `pool_file_key`、绝对地址 `pool_file_url`，并在策略生成时落地本地文件路径 `pool_file_local`（默认目录 `/app/user_pools_local`，可由 `AI_STRATEGY_LOCAL_POOL_ROOT` 覆盖）。
- 代码常量兜底：后端会在代码中兜底写入 `POOL_FILE_LOCAL/POOL_FILE_URL/POOL_FILE_KEY`，回测侧按“本地优先、远程兜底”解析，降低网络依赖。
- 入参支持：前端可直接传 `pool_file_url`；后端优先采用该绝对地址，未提供时再由 `pool_file_key` 自动推导。
- 超时治理：为规避网关层长连接超时，推荐优先使用 `generate-qlib/async + tasks/{task_id}` 异步模式；同步接口保留兼容。
- 任务持久化：异步任务状态会写入 Redis（键前缀默认 `quantmind:strategy:generate_qlib:task:`，TTL 默认 3600 秒），Engine 重启后仍可查询未过期任务。

## 策略保存说明（save-to-cloud）
- `save-to-cloud` 会上传策略代码到 COS（或本地存储），并将元数据统一写入数据库表 `strategies`（不再写 `user_strategies`）。
- 若设置 `STRATEGY_SYNC_ENABLED=false`，会跳过 strategy-service 同步，仅返回 COS 保存结果（用于本地联调或下游服务不可用时的降级运行）。
- 写入 `strategies` 时会保存：
  - `name/description/strategy_type/status`
  - `config.code` 与 `code`（便于 AI-IDE 远程读取与策略管理）
  - `cos_url/file_size/code_hash/tags/is_public`
- 远程策略读取接口 `GET /api/v1/strategy/remote/list` 与 `GET /api/v1/strategy/remote/{id}` 优先读取 `strategies`；历史 `user_strategies` 仅读兼容。
- `read_object` 已兼容自定义 COS 域名（如 `https://cos.quantmind.cloud/...`），并在对象键推断失败时回退为 HTTP 直读，避免“远程策略列表可见但代码为空”。

### 历史数据一次性迁移脚本

- 脚本路径：`backend/ai_strategy/scripts/migrate_user_strategies_to_strategies.py`
- 作用：将历史 `user_strategies` 记录一次性迁移到 `strategies`，并通过 `parameters.legacy_user_strategy_id` 做幂等去重。
- 推荐先预演：
  - `backend/ai_strategy/.venv/bin/python backend/ai_strategy/scripts/migrate_user_strategies_to_strategies.py --dry-run`
- 执行迁移：
  - `backend/ai_strategy/.venv/bin/python backend/ai_strategy/scripts/migrate_user_strategies_to_strategies.py`
- 常用参数：
  - `--user-id 00000001`：仅迁移指定用户
  - `--limit 100`：限制条数
  - `--allow-empty-code`：允许代码读取失败时仍迁移

### 股票池元数据历史回填脚本

- 脚本路径：`backend/services/engine/ai_strategy/scripts/backfill_stock_pool_files.py`
- 作用：扫描 COS `user_pools/` 前缀，幂等回填 `stock_pool_files` 元数据，修复历史“仅上传 COS、未写数据库”导致第二步无法复用的问题。
- 预演（不写库）：
  - `PYTHONPATH=/path/to/quantmind python backend/services/engine/ai_strategy/scripts/backfill_stock_pool_files.py --dry-run`
- 执行回填：
  - `PYTHONPATH=/path/to/quantmind python backend/services/engine/ai_strategy/scripts/backfill_stock_pool_files.py --apply`
- 常用参数：
  - `--user-id 00000001`：仅回填指定用户
  - `--max-files 500`：限制最大扫描数量
  - `--compute-stock-count`：读取对象正文并回填 `stock_count`

## Phase 2 新增功能

### 🔴 市场状态检测服务

实时检测市场环境，为策略生成提供动态仓位建议。

**特性**:
- 基于AKShare实时数据源
- 支持沪深300、上证指数等主流指数
- 自动计算收益率、成交量比率、波动率
- 提供熊市/震荡/牛市三级分类
- 1小时缓存，优化性能

**示例请求（示例/合成数据）**:
```bash
curl "http://localhost:8008/api/v1/strategy/market-state?symbol=000300&window=20"
```

**响应**:
```json
{
  "success": true,
  "data": {
    "state": "normal",
    "index_change": -0.0082,
    "volume_ratio": 1.12,
    "volatility": 0.1178,
    "recommendation": {
      "min_position": 0.5,
      "max_position": 0.7,
      "suggested_position": 0.6
    },
    "index_name": "沪深300"
  }
}
```

### 🟡 Qlib策略验证服务

5步安全验证流程，确保策略代码可靠性。

**验证步骤**:
1. Python语法检查（AST解析）
2. 导入安全检查（白名单+黑名单）
3. STRATEGY_CONFIG配置验证
4. 策略类定义检查（BaseStrategy继承）
5. 沙箱执行测试（subprocess隔离，10s超时）

**示例请求**:
```bash
curl -X POST "http://localhost:8008/api/v1/strategy/validate-qlib" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import pandas as pd\nfrom qlib.contrib.strategy.base import BaseStrategy\n...",
    "context": {"start_date": "2023-01-01", "universe_size": 300}
  }'
```

### 🟢 云端保存服务

将策略代码上传到腾讯云COS，支持个人中心访问。

**特性**:
- 双模式支持（Mock本地/真实COS）
- 自动计算文件哈希
- 元数据保存（条件、风险配置等）
- 生成访问路径
- 持久化写入 `user_strategies` 表
- 上传异常会记录日志并返回可读错误，便于定位配置问题

**示例请求**:
```bash
curl -X POST "http://localhost:8008/api/v1/strategy/save-to-cloud" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "strategy_name": "我的量化策略",
    "code": "...",
    "metadata": {"description": "动量策略", "tags": ["动量"]}
  }'
```

### 🟣 股票池保存与命名绑定

在“确定股票池”步骤，支持将用户自定义名称与 COS 绝对地址绑定保存。

**实现说明**:
- `save-pool-file/get-active-pool-file` 会写入/读取 `stock_pool_files` 表。
- 若运行环境缺少 `greenlet`（SQLAlchemy async 依赖），接口会使用同步 Session（连接池：`backend.shared.database_pool`）在后台线程执行 DB 操作，避免接口失败。
- `generate-qlib` 默认依赖通义千问（Qwen）生成代码；企业级金融业务禁止任何 mock/演示策略兜底。若 `QWEN_API_KEY` 缺失或外部接口不可用，请先完成真实模型服务配置后再进行联调。
- 为提升联调稳定性，`generate-qlib` 会对生成结果做一次 AST 语法解析；若检测到截断型语法错误（如括号未闭合），会自动触发 1-2 次最小修复重试。

**示例请求**:
```bash
curl -X POST "http://localhost:8008/api/v1/strategy/save-pool-file" \
  -H "Content-Type: application/json" \
	  -d '{
	    "tenant_id": "tenant_001",
	    "user_id": "user_123",
	    "pool_name": "自定义股票池_2026-02-05",
	    "format": "txt",
	    "pool": [{"symbol": "000001.SZ", "name": "示例/合成数据"}]
	  }'
```

**响应（含 COS 绝对地址）**:
```json
{
  "success": true,
  "pool_name": "自定义股票池_2026-02-05",
  "file_url": "https://cos.quantmind.cloud/stock_pools/...",
  "file_key": "stock_pools/...",
  "relative_path": "2026/02/05/stock_pool.csv"
}
```

## API文档

启动服务后访问Swagger文档：
```
http://localhost:8008/docs
```

交互式API文档包含所有接口的详细说明、参数定义和在线测试功能。

补充说明：`/api/v1/health` 会返回模型健康状态，并包含验证服务可用性字段。
基础存活检查可使用 `/health`（不走 v1 路由）。

## 路由收敛补充（2026-02-20）

- 为避免与统一策略接口冲突，`ai_strategy/api/v1/routes.py` 中旧版策略 CRUD 路由已迁移为：
  - `GET /api/v1/legacy/strategies`
  - `POST /api/v1/legacy/strategies`
  - `GET /api/v1/legacy/strategies/{strategy_id}`
  - `PUT /api/v1/legacy/strategies/{strategy_id}`
  - `DELETE /api/v1/legacy/strategies/{strategy_id}`
- 个人中心与云端策略统一走 `qlib_app/api/user_strategies.py` 的 `/api/v1/strategies*`（PG + COS）。


## 常见问题
*   **市值单位**: 数据库底层单位由 `AI_STRATEGY_TOTAL_MV_PER_YI` 决定（默认元，即 `1e8` 元 = 1 亿）；`parse-conditions` 会把前端“亿”口径换算到数据库 `total_mv`，而 `query-pool`/`preview-pool-file`/投研接口返回的 `market_cap` 统一为“亿元”，前端不应再二次除以 `1e8`。
*   **数据范围**: 该模块只保留近30天数据，请确保 ETL 任务持续补齐每日数据并定期清理历史行。

## 工具脚本：上传股票池到 COS

用于生成股票池列表文件并上传到腾讯云 COS（示例/合成数据，仅用于测试）。

```bash
python backend/ai_strategy/scripts/upload_stock_pool_to_cos.py \
  --user-id user_123 \
  --symbols "SH600519,SZ000001,SH600036"
```

从数据库读取股票列表并上传：

```bash
python backend/ai_strategy/scripts/upload_stock_pool_to_cos.py \
  --user-id user_123 \
  --from-db \
  --db-table stock_daily_latest \
  --db-column code
```

依赖环境变量（项目根目录 `.env` 优先）：
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION`
- `TENCENT_BUCKET`
- `TENCENT_COS_URL`（可选，用于拼接访问 URL）
也支持 `COS_SECRET_ID`/`COS_SECRET_KEY`/`COS_REGION`/`COS_BUCKET` 作为兼容变量。

如已配置私有域名（示例：`https://cos.quantmind.cloud`），请设置：
```bash
TENCENT_COS_URL=https://cos.quantmind.cloud
```
脚本会返回完整可访问链接。
*   **覆盖率口径**: 覆盖率以“候选全集大小”为分母，优先使用 `user_universe(user_id, ts_code)`（若存在且该用户有数据），否则退化为 `stock_daily_latest` 全量记录数；覆盖率被限制在 0-100% 之间，避免出现超过 100% 的异常显示。
*   **SQL兜底**: 若 LLM 生成了仅包含最新交易日、无筛选条件的 `stock_selection` 查询，会自动改写为 `stock_daily` 全量查询。
*   **stock_daily 字段扩展**: 支持 `name/is_st/idx_hs300/idx_zz1000`，并兼容旧字段别名，以便在全市场筛选中直接过滤 ST/指数成分股。
*   **查询源切换**: 选股查询逻辑已统一读取 `stock_daily_latest` 快照表（每股一行），并通过兼容层同时识别新旧字段名。
*   **快照表简化**: `stock_daily_latest` 已收敛为核心选股字段（价格、成交额、市值、PE/PB、ST/指数成分），移除技术指标与扩展财务字段。
*   **快照字段对齐（2026-05-03）**: `stock_daily_latest` 字段映射已与当前库结构对齐（`symbol/name/amount/idx_hs300/idx_zz1000`），并保留旧字段别名兼容历史 SQL。
*   **策略池统一口径（2026-05-08）**: `query-pool`、`preview-pool-file` 和 `research/symbols/features` 已统一返回 `market_cap` 为亿元，`PoolPreview` 不再对市值重复除以 `1e8`；全市场股票池也改为批量富化，避免固定截断前 500 只。
*   **股票池去重（2026-05-08）**: `save-pool-file` 现在会优先按内容哈希复用同一份 `txt` 股票池，重复同步不会再创建多条完全相同的历史记录。
*   **金融股解析修复（2026-03-03）**: “金融股/金融板块”本地解析改为“业务词本身 + 细分别名”双轨匹配（如 `金融/银行/保险/证券` 与 `证券、期货业`），避免仅匹配别名导致候选结果为 0。
*   **行业匹配增强（2026-03-03）**: 本地文本解析的行业筛选由单列 `industry` 升级为 `industry OR nindnme` 联合匹配，提升细分行业词（如“证券、期货业”）召回稳定性。
*   **解析策略**: 选股文本采用“本地优先 + 远程兜底”流程，本地规则命中则直接生成 DSL，未命中才调用 LLM；LLM 生成 SQL 会被强制改写为 `stock_daily_latest`。
*   **成交额字段**: 快照表当前使用 `amount` 字段表示成交额，同时兼容历史 `turnover` 写法。
*   **布尔条件**: DSL 同时支持 `==` 与 `=`；`is_st/idx_hs300/idx_zz1000` 等布尔字段会将 0/1 转为布尔值比较。
*   **空值处理**: `is_st/idx_hs300/idx_zz1000` 若为 NULL，查询时按 `0/false` 处理，避免全量过滤为空。
