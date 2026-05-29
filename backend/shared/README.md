# backend/shared — 跨服务共享模块

所有核心集群（quantmind-api / engine / trade / stream）可复用的工具库。

## 模块一览

| 文件 | 用途 |
|------|------|
| `strategy_storage.py` | **统一策略存储服务**（PG + COS），见下节 |
| `notification_publisher.py` | **统一通知发布器**（best-effort 写入 notifications） |
| `cos_service.py` | 腾讯云 COS SDK 封装（上传/下载/预签名/删除） |
| `cos_config.py` | COS 配置加载与校验（从环境变量读取） |
| `database_pool.py` | SQLAlchemy 连接池（仅 PostgreSQL，支持 asyncpg / psycopg2） |
| `storage_resolver.py` | 本地路径 / COS Key / 数据库 ID 的抽象解析器 |
| `api_spec.py` | 标准 API 响应模型与 OpenAPI 规范辅助 |
| `margin_stock_pool.py` | 固定融资融券股票池加载与判定服务，支持 `xlsx/txt` 两种来源 |
| `qmt_bridge_auth.py` | QMT Bridge 会话 token 共享鉴权与续期（供 trade/stream 复用） |
| `model_registry.py` | 用户模型注册、默认模型、策略绑定与系统兜底解析 |

---

## StorageResolver 兼容（2026-03-11）

- `storage_resolver.py` 现支持将 `https://.../user_pools/.../stock_pool.txt` 这类绝对 URL 自动归一化为 COS Key 后解析。
- 同时兼容 `cos://` 前缀与历史 key 形式，便于回测侧直接使用 `POOL_FILE_URL`。

## Bridge 会话鉴权下沉（2026-04-02）

- 新增 `qmt_bridge_auth.py`，统一承载 `bridge_session_token` 的：
  - token 哈希与生成
  - 会话创建/吊销/校验
  - 会话刷新（refresh rotation）
- `quantmind-stream` 不再直接依赖 `trade.services.qmt_agent_auth`，改为依赖 shared 层能力，降低跨服务代码耦合。

## Access Log 兼容性（2026-04-02）

- `request_logging.py` 对 `uvicorn` 不同版本的断连异常做了兼容处理：
  - 旧版本继续识别 `ClientDisconnected`
  - 新版本回退识别 `EndOfStream/ConnectionResetError/BrokenPipeError`
- 目标是保证 access middleware 在不同运行时版本下都能稳定返回 `499`，避免因导入路径变化导致服务启动失败。

## ModelRegistryService（2026-04-04）

- `model_registry.py` 统一承载用户模型注册、默认模型设置、策略绑定和模型解析。
- 默认模型支持两类来源：
  - 用户训练后注册的模型
  - `models/production` 下的系统内置模型
- 推理解析优先级为：`显式模型 > 策略绑定 > 用户默认 > 系统兜底`。
- 当前前端模型管理页已提供轻量级 `设默认` 按钮，可直接将系统内置模型设为默认模型。

## TradingCalendarService（2026-04-07）

- 新增 `trading_calendar.py`，提供跨服务统一交易日历能力，避免 `trade/engine/stream` 各自硬编码“周一到周五”规则。
- 核心能力：
  - `is_trading_day(market, date, tenant_id, user_id)`
  - `is_trading_time(market, datetime, tenant_id, user_id)`
  - `next_trading_day / prev_trading_day`
  - `get_sessions(market, date, tenant_id, user_id)`
  - `batch_is_trading_day`
- 多租户覆盖优先级：
  - `tenant_id + user_id`（用户级覆盖）
  - `tenant_id + '*'`（租户级覆盖）
  - `default + '*'`（全局默认）
- 数据库表：
  - `qm_market_calendar_day`
  - `qm_market_trading_session`
  - `qm_market_calendar_exception`
  - `qm_market_calendar_version`
- 回退策略：
  - 缺少显式日历数据时，优先尝试 `exchange_calendars`（SSE/SZSE/CFFEX 映射 `XSHG`）；
  - 依赖不可用时降级为“工作日规则”。

## StrategyStorageService（核心）

`strategy_storage.py` 是**所有策略读写的唯一入口**，实现：

```
保存 → 上传代码到 COS（私读）→ UPSERT PG strategies 表（元数据 + cos_key）
读取 → 从 PG 查 cos_key → 生成预签名 URL（TTL 3600s）→ 按需从 COS 拉代码
```

### 快速使用

```python
from backend.shared.strategy_storage import get_strategy_storage_service

svc = get_strategy_storage_service()   # 全局单例

# 保存（异步）
result = await svc.save(
    user_id="00000001",   # 业务用户 ID（自动解析为 DB int ID）
    name="策略名称",
    code="...python code...",
    metadata={
        "strategy_type": "QUANTITATIVE",  # 枚举：大写
        "status": "ACTIVE",               # 枚举：ACTIVE / DRAFT
        "tags": ["qlib", "动量"],
        "description": "...",
    }
)
# → {"id": "17", "cos_key": "user_strategies/.../xxx.py", "cos_url": "https://...", ...}

# 列表（同步，返回 created_at/updated_at）
strategies = svc.list(user_id="00000001")

# 详情含代码（异步）
detail = await svc.get(strategy_id=17, resolve_code=True)

# 更新（异步，代码变更时重新上传 COS）
await svc.update(strategy_id=17, user_id="00000001", code="...new code...")

# 软删除
svc.delete(strategy_id=17, user_id="00000001")
```

### COS Key 格式

```
user_strategies/{user_id}/{yyyy}/{mm}/{uuid}.py
```

### 数据库驱动兼容注意事项

> **重要**：`strategy_storage.py` 使用**独立的同步 psycopg2 引擎**（通过 `_build_sync_db_url()` 自动从 `DATABASE_URL` 环境变量中将 `asyncpg` 替换为 `psycopg2`）。
>
> 原因：Docker 容器中 `database_pool` 注册的是 asyncpg 异步引擎，而策略存储服务是同步阻塞 I/O；两者共用同一引擎会导致冲突。通过内置独立引擎彻底解耦。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | 从 DB_* 变量拼接 | PG 连接串（含 asyncpg 时自动替换驱动） |
| `DB_MASTER_HOST / PORT / USER / PASSWORD / NAME` | — | 分解型配置（优先级低于 DATABASE_URL） |
| `REDIS_HOST / REDIS_PORT / REDIS_PASSWORD / REDIS_DB` | — | Redis 统一连接配置（缓存/Celery/消息队列） |
| `STORAGE_MODE` | `cos` | `cos`=PG+COS；`local`=纯 PG（无 COS 上传） |
| `COS_STRATEGY_URL_TTL` | `3600` | 预签名 URL 有效期（秒） |
| `TENCENT_COS_TIMEOUT / COS_TIMEOUT` | `60` | COS SDK 上传/下载请求超时（秒） |

### 环境变量优先级（2026-03 更新）

- 统一策略：`运行时环境变量` > `项目根 .env` > `代码默认值`。
- `backend/shared/config_manager.py` 与 `backend/shared/database_manager_v2.py` 使用 `load_dotenv(..., override=False)`。
- `backend/shared/unified_config.py` 在读取 `.env` 时仅补齐缺失变量（`os.environ.setdefault`），不会覆盖运行时注入值。
- 在 Docker 场景中，容器启动时通过 `environment` 注入的上游地址（如 `TRADE_SERVICE_URL`、`ENGINE_SERVICE_URL`）不会再被根 `.env` 覆盖。

### Pydantic / SQLAlchemy 兼容（2026-03 更新）

- `backend/shared` 内用于跨服务导入的 Pydantic 模型已统一迁到 `ConfigDict` 写法。
- 共享 ORM 基类统一使用 `sqlalchemy.orm.declarative_base()`，避免 SQLAlchemy 2.x 弃用告警扩散到服务启动和 CI。

### PG strategies 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | serial PK | 策略数字 ID |
| `user_id` | int FK | 归属用户 |
| `cos_key` | text | COS 对象键（唯一定位代码） |
| `cos_url` | varchar(500) | 上次生成的预签名 URL（仅供参考，应实时重新生成） |
| `code` | text | 代码副本（`resolve_code=False` 时的降级来源） |
| `strategy_type` | enum | `TECHNICAL / FUNDAMENTAL / QUANTITATIVE / MIXED` |
| `status` | enum | `DRAFT / REPOSITORY / LIVE_TRADING / ACTIVE / PAUSED / ARCHIVED` |

### 生命周期状态更新（2026-03-09）

- `StrategyStorageService` 新增：
  - `update_lifecycle_status(strategy_id, user_id, status) -> bool`
- 用途：
  - 供实盘启停链路异步回写策略生命周期状态（`draft/repository/live_trading`）。
- 规则：
  - 输入状态会归一化并映射到数据库枚举（兼容 `ACTIVE/REPOSITORY`）；
  - 仅更新当前用户且未归档策略；
  - 非数字策略ID会安全跳过并记录警告日志。

### 通知发布器（2026-03-09）

- 新增 `notification_publisher.py`：
  - `publish_notification(...)`：同步写入通知（best-effort，失败不抛异常阻断业务）。
  - `publish_notification_async(...)`：异步线程池包装，供 `trade/engine` 事件链路调用。
- 字段口径统一：`user_id/tenant_id/title/content/type/level/action_url`。
- 兼容缺表场景：`notifications` 表缺失时仅记录 warning，不影响主流程。
- 兼容外键场景（2026-03-14）：当 `notifications.user_id -> users.user_id` 外键不满足（如用户不存在）时，发布器会降级为 `skipped` 并记录 warning，不抛异常阻断交易/策略主链路。
- 实时通知扩展（2026-03-10）：
  - 写库成功后会追加 Redis Stream `notification_events`；
  - 新增 `notification_metrics.py` 统一暴露通知发布、事件推送、未读查询与 WS 下发指标；
  - Redis 事件推送失败不会回滚主业务写库结果。

---

## 单元测试

```bash
source .venv/bin/activate
python -m pytest backend/shared/tests/test_strategy_storage.py -v   # 15 项
```

---

## 数据库 Migration

首次部署或升级前，执行：

```bash
PGPASSWORD=$DB_PASSWORD psql -h $DB_MASTER_HOST -U $DB_USER -d $DB_NAME \
  -f backend/migrations/add_strategies_cos_key.sql
```

该脚本为 `strategies` 表添加 `cos_key` 字段及四个查询索引，并从历史 `cos_url` 反推 `cos_key`（无历史数据时自动跳过）。

兼容说明：
- 运行期若检测到 `strategies.cos_key` 尚未迁移，`strategy_storage.py` 会自动降级为“不含 cos_key 列”的 SQL 路径，避免 `save/list/get/update` 直接报 `UndefinedColumn`。
- 仍建议尽快执行上述 migration，以启用基于 `cos_key` 的完整能力（唯一定位与预签名读取链路）。
