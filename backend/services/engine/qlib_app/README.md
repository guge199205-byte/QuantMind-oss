# qlib_app 模块规范

本模块是 Qlib 引擎的业务适配层，负责 API 路由、策略生命周期管理及结果持久化。

## API 路由拆分

为降低 `api/backtest.py` 的单文件复杂度，当前 Qlib 路由已按职责拆分为多个子模块，外部路径保持不变：

- `api/backtest.py`：仅保留回测执行入口
- `api/optimization.py`：网格搜索和遗传算法优化
- `api/ai_fix.py`：AI 策略修复
- `api/history.py`：结果查询、历史列表、删除、对比、状态
- `api/export.py`：回测导出
- `api/ops.py`：健康检查、任务状态、日志、进度回传、前端错误转发
- `api/risk.py`：风险指标、风险预警、风险配置
- `api/identity.py`、`api/task_info.py`、`api/strategy_name.py`、`api/history_filters.py`、`api/export_utils.py`：供路由复用的窄职责工具
- `services/backtest_service.py`：回测服务入口与初始化
- `services/backtest_service_runtime.py`：回测运行主链路
- `services/backtest_service_query.py`：回测结果、状态、历史、删除、对比、进度通知

## 近期收口（2026-04-10）
- `services/user_strategy_loader.py`、`services/strategy_builder.py` 的策略加载、存储回退、参数补全与模板构建日志已统一为结构化事件格式；
- `utils/strategy_adapter.py` 的参数清洗/路径解析日志，以及 `websocket/connection_manager.py` 的连接与广播日志也已统一收口；
- `api/backtest.py` 的回测入口异常日志同样改为结构化事件格式，便于与任务、分析、风控链路共用同一排障口径。
- `tasks.py` 的 Redis 连接、优化锁释放、进度上报失败、任务成功/失败回调与前端错误转发日志也已统一为结构化事件格式；
- 这样 Celery worker、回测入口与前端错误上报现在共享同一套日志 schema，便于在 Redis、worker 控制台和前端结果区做一致排障。

## 对比接口优化（2026-04-08）

- `compare_backtests` 现在只拉取回测摘要字段，不再加载 `equity_curve/trades/positions` 等大字段；
- 返回结果同时兼容 `backtest1/backtest2` 与旧字段 `result_1/result_2`；
- 前端策略对比页只消费摘要指标，避免整份回测结果拖慢加载。

后续新增路由时，优先按领域继续拆分，不再向 `backtest.py` 中堆积。

## 修复记录（2026-03-27，自动推理暂停开关）
- 新增 Celery Beat 开关：`AUTO_INFERENCE_ENABLED`（默认 `true`）。
- 当设置为 `false` 时，不注册 `engine.tasks.auto_inference_if_needed` 的 08:55 定时调度，仅暂停自动推理，不影响手动触发和其他异步任务。

## 修复记录（2026-04-10，低频分析服务日志收口）
- 因子分析、回测报告生成、风格归因、绩效分析、持仓分析与市场状态服务的关键日志已统一成结构化事件格式；
- 这些服务现在与回测主链路、风控与交易统计一样，优先输出 `event=... key=value`，便于统一检索和排障。

## 修复记录（2026-04-10，风险分析日志收口）
- `risk_analyzer.py` 的关键告警与兜底日志已统一为结构化事件格式；
- 因子、交易、持仓、基准与高级统计相关的异常现在按同一 schema 输出，方便统一排障与回溯。

## 修复记录（2026-04-10，工具与查询日志收口）
- `strategy_templates.py`、`backtest_service_query.py`、`strategy_formatter.py`、`cache_manager.py`、`websocket.py` 的关键日志已统一为结构化事件格式；
- 模板加载、缓存读写、信号格式修复、回测结果查询与 WebSocket 访问控制现在共用同一排障口径。

## 修复记录（2026-04-10，回测与运维日志收口）
- `backtest_service.py`、`backtest_persistence.py`、`risk_monitor.py`、`admin_templates.py`、`reports.py`、`ops.py` 的关键日志已统一为结构化事件格式；
- 回测初始化、COS 冷备、风险监控、管理员模板变更、报告导出与任务运维现在共用同一排障口径。

## 修复记录（2026-04-10，回测运行与优化日志收口）
- `backtest_service_runtime.py`、`genetic_optimization_service.py`、`trade_stats_service.py` 的关键日志已统一为结构化事件格式；
- 回测执行、遗传优化评估、收敛检测与交易统计回退现在共用同一排障口径。

## 修复记录（2026-03-27，实盘状态回源地址）
- `GET /api/v1/strategies` 读取实盘运行态时，会调用 `trade` 的 `/api/v1/real-trading/status`。
- 新增容器内地址保护：当 `TRADE_SERVICE_URL` 被配置为 `127.0.0.1/localhost` 且运行在 Docker 容器时，自动回退到 `http://quantmind-trade:8002`，避免误指向 engine 容器自身。
- 线上 compose 仍应显式设置：
  `TRADE_SERVICE_URL=http://quantmind-trade:8002`（以服务发现地址为准，不依赖 `.env` 本地开发值）。

## 📁 策略存储架构（PG + COS 统一版，2026-02-19）

所有策略读写已统一通过 `backend.shared.strategy_storage.StrategyStorageService`，不再直接操作文件系统：

```
保存 → 代码上传至 COS（私读）→ UPSERT PG strategies 表（元数据 + cos_key）
读取 → PG 查 cos_key → 生成预签名 URL（TTL=3600s）→ 按需从 COS 下载代码
```

**策略端点** → `api/user_strategies.py`（已重写）  
**存储服务** → `../../shared/strategy_storage.py`（唯一入口，详见 [backend/shared/README.md](../../shared/README.md)）

### COS Key 格式

```
user_strategies/{user_id}/{yyyy}/{mm}/{uuid}.py
```

### strategies 表枚举值（必须大写）

| 字段 | 合法值 |
|------|--------|
| `strategy_type` | `TECHNICAL / FUNDAMENTAL / QUANTITATIVE / MIXED` |
| `status` | `DRAFT / REPOSITORY / LIVE_TRADING / ACTIVE / PAUSED / ARCHIVED` |

## 📂 策略代码加载（user_strategy_loader.py）

`services/user_strategy_loader.py` 已重写，优先从 PG 加载，文件系统为 `STORAGE_MODE=local` 时的兜底。

## ⚙️ 关键配置

- **Redis 认证**：统一使用 `get_redis_sentinel_client`，自动读取 `.env` 中的 `REDIS_PASSWORD`。
- **数据源指向**：`QLIB_PROVIDER_URI` 默认为 `db/qlib_data`，启动时验证 `instruments`/`calendars` 完整性。
- **COS 凭证**：`TENCENT_SECRET_ID / KEY / REGION / BUCKET`（从 DB system_settings 或 `.env` 读取）。

## 双向交易策略参数（2026-03-15）

`QlibStrategyParams` 已增加以下后端参数，用于由策略配置驱动双向交易：

- `enable_short_selling`
- `margin_stock_pool`
- `financing_rate`
- `borrow_rate`
- `max_short_exposure`
- `max_leverage`

当前仅扩展后端 Schema 与执行参数透传，前端回测中心不新增融资融券切换入口。

## 🧪 验证脚本

- `scripts/verify_engine_v2.py`: 综合功能验证（IC、归因、建议、进度）。
- `scripts/compare_topk_2024_models.py`: 对比 `models/model_preview/alpha158.txt` 与生产 `pred.pkl` 在 2024 年 TopK 回测表现（通过后端 `QlibBacktestService` 执行）。
- `backend/scripts/seed_qlib_strategy.py`: 播种 Qlib 示例策略到指定用户的云端策略中心。

### 2024 TopK 模型对比脚本

```bash
source .venv/bin/activate
PYTHONPATH=/Users/qusong/git/quantmind \
python backend/services/engine/qlib_app/scripts/compare_topk_2024_models.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --topk 50 \
  --n-drop 5 \
  --universe all
```

输出：
- 终端打印 alpha158 vs production 的关键指标对比（总收益、年化、夏普、回撤等）
- 产物落盘到 `models/model_preview/compare_reports/`（含两份 `pred.pkl` 切片和 JSON 对比报告）

## 📋 Qlib 示例策略

运行以下命令可向任意用户的策略中心写入一条可运行的 Qlib 动量示例策略：

```bash
source .venv/bin/activate
PYTHONPATH=/path/to/quantmind \
POSTGRES_URL="postgresql+psycopg2://quantmind:<password>@localhost:5432/quantmind" \
python backend/scripts/seed_qlib_strategy.py
```

策略内容：20日动量 + 等权重再平衡，基于 `TopkDropoutStrategy`，支持 csi300 回测。

## 修复记录（2026-02-20）

- 修复 `api/user_strategies.py` 中 `_get_user_id` 缺失 `import os` 导致的运行时 `500`（网关注入 `X-Internal-Call` 鉴权头时触发）。

## 修复记录（2026-02-21）

- 修复 Celery 异步回测 ID 断链：
  - `QlibBacktestRequest` 增加 `backtest_id` 透传字段；
  - 避免 worker 执行阶段重新生成 ID，导致 `POST /qlib/backtest?async_mode=true` 与 `GET /qlib/backtest/{id}/status` 对不上。
- 修复 Celery 数据路径解析：
  - `qlib_app/tasks.py` 相对路径基准改为项目根目录，避免错误解析为 `backend/db/qlib_data/day`。
- 修复 Redis 鉴权口径：
  - 异步日志采集与 `/qlib/health`、`/qlib/logs/{backtest_id}` 统一带 `REDIS_PASSWORD`，并兼容 `REDIS_DB_DEFAULT` 回退。
- 修复网格优化异步任务返回空结果：
  - `qlib_app/tasks.py` 的 `run_optimization_async` 从占位实现改为真实执行 `OptimizationService.run_optimization`；
  - Celery `SUCCESS` 元数据统一写入 `meta.result`，前端轮询可拿到 `all_results/best_params/target_metric`，支持参数优化结果展示与回填。

## 修复记录（2026-02-24）

- 统一 Qlib 默认数据目录：
  - `qlib_app/main.py` 与 `qlib_app/tasks.py` 的默认 provider 路径统一为 `db/qlib_data`；
  - 避免旧默认值 `research/data_adapter/qlib_data` 与当前数据布局不一致导致初始化失败。

## 修复记录（2026-03-03）

- 修复 `api/user_strategies.py` 错误码透传：
  - `list/get/activate/deactivate` 接口增加 `except HTTPException: raise`；
  - 避免 `401/404` 被通用异常捕获后错误包装为 `500`，保证网关与前端拿到正确状态码。
- 修复 Celery Worker 启动链路：
  - `celery_config.py` 的 `imports/autodiscover_tasks` 收敛为仅加载 `backend.services.engine.qlib_app` 任务；
  - 避免 worker 启动时强制导入 `engine.tasks` 触发 `duckdb` 缺失导致的进程崩溃。

## 修复记录（2026-03-07）

- 修复本机开发模式下 Celery Redis 主机名不可达：
  - `celery_config.py` 新增 Redis 主机名自适配逻辑；
  - 当宿主机进程读到 `REDIS_HOST=quantmind-redis/redis` 且不可解析时，自动回退 `host.docker.internal -> 127.0.0.1 -> localhost`；
  - 解决 `POST /api/v1/qlib/backtest?async_mode=true` 因 broker 连接失败返回 `503` 的问题（Docker 内运行不受影响）。

## 修复记录（2026-03-08）

- 修复实时订阅鉴权与归属校验：
  - `/api/v1/ws/backtest/{backtest_id}` 与 `/api/v1/ws/risk-monitor/{backtest_id}` 增加 token 校验与 `user_id + tenant_id` 归属检查，阻断跨租户订阅风险。
- 修复优化日志键前缀不一致：
  - `tasks.py` 中网格/遗传优化日志统一写入 `qlib:logs:{tenant_id}:{optimization_id}`，与 `/qlib/logs/{id}` 查询口径对齐。
- 修复日志接口错误语义：
  - `/qlib/logs/{id}` 不再吞异常返回 `200`，Redis 不可用时返回 `503`，便于前端与监控正确感知故障。
- 日志捕获改为任务级 handler：
  - `tasks.py` 不再依赖进程级全局 stdout/stderr 替换，而是为每个任务单独挂载 Redis logging handler；
  - `print` 与标准 logging 都会写入当前任务的 Redis 日志 key，且每条日志前缀会带上 `backtest_id / optimization_id / task_id / tenant_id / user_id` 等上下文，降低多任务并发时的串流风险并便于排障。
  - Celery 任务回调日志也已统一为固定格式（`[celery-task] status=... task_id=...`），便于 worker 控制台与 Redis 日志保持一致。
- 回测与优化主链路日志进一步结构化：
  - `backtest_service_runtime.py`、`optimization_service.py`、`genetic_optimization_service.py` 的关键运行日志统一收敛为 `event=... key=value` 形式；
  - 遗传优化链路已取消旧式 Redis 重复推送，统一由任务级 handler 写入当前任务日志 key，避免双写与口径分裂。
- 次级 API 与分析链路继续收口：
  - `api/analysis.py`、`api/risk.py`、`api/risk_monitor.py`、`api/user_strategies.py` 的关键接口日志也已统一为结构化事件格式；
  - 风控、分析、策略激活与同步类接口都优先输出 `event=... key=value`，降低排障时的日志搜索成本。

## Celery 并发与提速（2026-02-21）

- `qlib_app/celery_config.py` 已支持通过环境变量调优任务执行参数：
  - `CELERY_TASK_TIME_LIMIT`（默认 `3600`）
  - `CELERY_TASK_SOFT_TIME_LIMIT`（默认 `3300`）
  - `CELERY_WORKER_PREFETCH_MULTIPLIER`（默认 `1`）
  - `CELERY_WORKER_MAX_TASKS_PER_CHILD`（默认 `10`）
  - `CELERY_WORKER_DISABLE_RATE_LIMITS`（默认 `false`）
  - `CELERY_TASK_ACKS_LATE`（默认 `true`）
  - `CELERY_TASK_REJECT_ON_WORKER_LOST`（默认 `true`）
  - `CELERY_RESULT_EXPIRES`（默认 `86400`）

- 推荐多进程启动命令（CPU 密集回测）：

```bash
source .venv/bin/activate
python -m celery -A backend.services.engine.qlib_app.celery_config:celery_app \
  worker -Q qlib_backtest -l info --pool=prefork --autoscale=12,4
```

说明：`prefork` 为多进程池；`autoscale=12,4` 表示最少 4 进程，最大 12 进程，可按机器 CPU/内存调整。

## 修复记录（2026-03-09）

- Celery 回测队列隔离（防跨环境抢任务）：
  - 新增环境变量 `QLIB_CELERY_QUEUE`（默认 `qlib_backtest`），并用于 `task_default_queue` 与 `task_routes`。
  - 服务器建议设置为独立值（如 `qlib_backtest_srv`），避免本机 worker 与服务器共享队列。
  - 支持可选变量 `QLIB_CELERY_EXCHANGE`、`QLIB_CELERY_ROUTING_KEY`。
- docker-compose 的 engine-worker 启动命令已改为读取 `QLIB_CELERY_QUEUE`。

## 修复记录（2026-03-09，策略监控状态聚合）

- `GET /api/v1/strategies` 新增运行态聚合：
  - 引擎侧会调用 `trade` 的 `/api/v1/real-trading/status`（透传 `Authorization`）识别当前活跃实盘策略；
  - 返回新增字段：`base_status`、`runtime_state`、`effective_status`；
  - 兼容旧字段：`status` 仍返回，并对齐为 `effective_status`。
- 状态口径统一：
  - 生命周期：`draft/repository/live_trading`（由策略表持久化）；
  - 运行态：`running/starting/stopped/error`（实时）；
  - 展示态：优先 `runtime_state`，无实时态时统一映射为 `stopped`。
- 运行态匹配增强（2026-03-20）：
  - 活跃策略匹配不再仅依赖 `strategy.id`，新增回退匹配 `sys_模板ID -> parameters.strategy_type` 与 `strategy.name`；
  - 修复“实盘容器已运行，但策略列表全部显示已停止”的映射缺失问题。

## 修复记录（2026-03-09，回测结果通知）

- `QlibBacktestService.run_backtest` 在回测终态新增通知发布：
  - `completed`：发布“回测已完成”通知（`type=strategy`）；
  - `failed`：发布“回测执行失败”通知（`type=strategy`）。
- 发布方式：统一调用 `backend.shared.notification_publisher.publish_notification_async`（best-effort）。

## 修复记录（2026-03-09，云端策略创建时间）

- `GET /api/v1/strategies` 返回项已补充 `created_at` 字段透传（此前仅返回 `updated_at`）。
- 修复后用户中心“云端策略管理”创建时间不再因空值被前端误格式化为 `1970/1/1 08:00:00`。

## 修复记录（2026-03-19，策略监控收益对齐）

- `GET /api/v1/strategies` 现在会按 `qlib_backtest_runs.config_json->>'strategy_id'` 聚合每个策略最近一次回测摘要：
  - 回填 `total_return`、`today_return`、`risk_level`、`error_message`、`error_code`、`last_update` 等字段；
  - 避免前端策略监控卡片仅依赖默认值，造成“看起来有收益、实际全是 0”的口径漂移。
- 对于当前正在运行的实盘策略，`today_return` 会优先用 trade 服务 `/api/v1/real-trading/status` 返回的组合实时 `daily_pnl/daily_return` 覆盖，确保监控卡显示的是实时收益而不是回测摘要。
- 同步会回填 `today_pnl`，前端监控卡可同时展示今日收益率与今日盈亏绝对值。
- 前端监控卡已切回自动刷新，运行态展示口径收敛为 `running / starting / stopped / error`，不再把“暂停”当作独立统计维度。

## 修复记录（2026-03-12，网格搜索任务状态 500）

- 修复 Celery 失败回调日志异常：
  - `qlib_app/tasks.py` 中 `CallbackTask.on_failure` 的 `exc_info` 改为标准化三元组，避免非标准异常对象触发日志格式化报错。
- 修复任务状态查询稳健性：
  - `get_backtest_status(task_id)` 对 `result.info / result.successful() / result.failed()` 增加异常保护，避免任务元信息异常导致状态接口抛错。
- 修复状态接口序列化兜底：
  - `GET /api/v1/qlib/task/{task_id}/status` 增加 task info 清洗逻辑，将异常对象与不可序列化结构转换为安全 JSON 结构，降低轮询阶段 `500` 风险。
- 修复 Celery 失败态写入兼容性：
  - `tasks.py` 中异常分支不再使用 `update_state(state=\"FAILURE\", meta=dict)`；改为 `PROGRESS + status=failed` 后再抛异常，由 Celery 标准机制落失败结果，避免 `Exception information must include the exception type`。
- 修复任务配置快照序列化：
  - `_to_jsonable` 升级为递归转换，支持嵌套 Pydantic 模型/列表/字典，避免 `QlibBacktestRequest is not JSON serializable`。

- `services/backtest_service_query.py` = 回测结果、状态、历史、删除、对比与进度通知
