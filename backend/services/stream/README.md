# Stream Gateway (`quantmind-stream`)

实时行情接入 + WebSocket 推送服务。

## 修复记录（2026-04-02，Bridge 鉴权依赖收敛）
- `ws_core` 的 `bridge_session_token` 校验已改为复用 `backend.shared.qmt_bridge_auth`。
- `stream` 不再直接 import `trade.services.qmt_agent_auth`，降低跨服务实现级耦合，保持“通过共享层复用能力”的边界约束。

- **入口**：`backend/services/stream/main.py`
- **端口**：`8003`
- **数据库配置来源**：仅项目根目录 `.env`（服务目录 `.env` 不再维护 `DATABASE_URL`）。
  - 优先读取：`DATABASE_URL`（或 `MARKET_DATA_DB_URL`）。
  - 回退拼接：`DB_DRIVER/DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`。
  - 驱动归一化时会保留原始密码，不再出现 URL 规范化后被 `***` 掩码导致的连接失败。
- **CORS 策略**：开发/测试环境默认允许本机前端源；生产/预发环境必须显式配置 `CORS_ALLOWED_ORIGINS`（或兼容变量 `CORS_ORIGINS`）白名单，禁止 `*`。

## 模块边界（P1）
- `stream` 负责行情读写与实时推送：行情 REST + WebSocket 发布订阅。
- 路由归属：`/api/v1/quotes/*`、`/api/v1/klines/*`、`/api/v1/symbols`、`/ws`（主入口）与 `/api/v1/ws/market`（兼容入口，同核心实现）。
- 新增内部桥接派发路由：`POST /api/v1/internal/bridge/order`，供 `quantmind-trade` 将 REAL 订单推送到已连接的 `bridge_session` 客户端（QMT Agent）。
  - bridge 连接匹配对纯数字 `user_id` 做归一化比较（`1` 与 `00000001` 视为同一用户），避免跨服务 user_id 表示格式差异导致误判离线。
  - bridge 握手元数据现显式记录 `session_id`，便于连接唯一性判断与排障。
  - 同一 `binding_id` 建立新 bridge 连接后，旧连接会被主动清理；内部派单与撤单只会路由到最新活动连接，避免重复下单。
- `stream` 可依赖本地缓存/远程行情源，但不承担用户认证入口、策略生成与交易执行。
- 禁止范围：不在 `stream` 内实现订单、持仓、回测、策略 CRUD 等业务。
- P3 可观测性基线：统一注入并透传 `X-Request-ID` 响应头，便于跨服务链路追踪。
- P3 错误契约：统一错误结构 `error.code/error.message/error.request_id`，并兼容保留 `detail` 字段。
- P3 日志基线：统一访问日志字段 `service/request_id/tenant_id/user_id/method/path/status/duration_ms`。
- P3 启动降级语义：市场库初始化失败时服务继续启动并记录 `warning`，`/health` 返回 `status=degraded` 且 `market_db=disconnected`（不再误报已连接）。
- P3 监控接入：新增 `/metrics` Prometheus 暴露，输出 `stream_market_db_connected` 与 `stream_service_degraded`，支持对降级状态做告警。
- P3 指标对齐：同步暴露 `quantmind_service_health_status{service="quantmind-stream"}` 与 `quantmind_service_degraded{service="quantmind-stream"}`，便于四服务统一面板。
- P3 兼容清理：`market_app` 的 Pydantic 响应模型已切到 `ConfigDict(from_attributes=True)`，ORM 基类切到 `sqlalchemy.orm.declarative_base()`，避免 Pydantic V2 / SQLAlchemy 2.x 弃用告警污染 CI。
- WebSocket 推送闭环：`ws_core.server` 生命周期已接入 `quote_pusher` 启停；客户端订阅 `stock.{code}` 后会触发行情拉取与推送。
- 通知实时链路（2026-03-10）：
  - `publish_notification_async()` 写库成功后会追加 Redis Stream `notification_events`；
  - `ws_core.notification_pusher` 消费该流并向 `notification.{user_id}` 主题推送用户站内通知；
  - 前端通知中心采用“HTTP 首屏 + WebSocket 增量”模式。
  - 配套规则：`config/prometheus/alerts/application.yml` 中新增 `StreamServiceDegraded` 与 `StreamMarketDBDisconnected`。

---

## 目录结构

```
services/stream/
├── main.py                     # FastAPI 应用入口（lifespan 管理）
├── market_app/                 # 行情 REST 服务层
│   ├── api/v1/
│   │   ├── quotes.py           # GET /api/v1/quotes/{symbol}
│   │   ├── klines.py           # GET /api/v1/klines/{symbol}
│   │   ├── symbols.py          # GET /api/v1/symbols
│   │   └── websocket.py        # 旧版示例实现（保留文件，不挂载路由）
│   ├── services/
│   │   ├── data_source.py      # DataSourceAdapter 基类 + Tencent/Sina 实现
│   │   ├── remote_redis_source.py  # ★ 远程 Redis 行情快照数据源（主力）
│   │   ├── ifind_source.py     # 同花顺 iFind HTTP 数据源
│   │   ├── quote_service.py    # 行情业务逻辑（缓存→最近落库→数据源→DB）
│   │   └── kline_service.py    # K 线业务逻辑
│   ├── models/                 # SQLAlchemy ORM（Quote / KLine / Symbol）
│   ├── schemas/                # Pydantic 请求/响应模型
│   └── market_config.py        # 服务配置（Pydantic Settings）
└── ws_core/                    # WebSocket 推送核心引擎
    ├── server.py               # 服务器生命周期 + 统一 WS 协议处理（/ws）
    ├── manager.py              # 连接/订阅管理器（UUID per connection）
    ├── message_queue.py        # 异步优先级消息队列（背压控制）
    ├── quote_pusher.py         # ★ 实时行情推送（读远程 Redis + 写序列 + 落库）
    └── indicator_pusher.py     # 技术指标推送（MACD/RSI/BOLL 等）
```

---

## 数据流

```
外部行情快照推送（建议每 30 秒）
        ↓
行情专用 Redis  market:snapshot:{symbol}
  { Now, PreClose, Open, High, Low, Volume, Amount, timestamp }
        ↓  RemoteRedisDataSource
QuotePusher（ws_core）
  ├─→ Redis ZSET market:series:{symbol}（时序序列）
  ├─→ PostgreSQL quotes（落库）
  └─→ manager.publish("stock.{code}") → WebSocket /ws
        ↓
QuoteService（REST）
  优先读最近落库 → 不命中再走数据源
        ↓
/api/v1/quotes/{symbol}
```

---

## 数据源

| 数据源 | 标识 | 状态 | 说明 |
|--------|------|------|------|
| **远程 Redis 快照** | `remote_redis` | ✅ **默认** | 按 `docs/行情快照写入规范.md` 推送 `market:snapshot:{symbol}` |
| 同花顺 iFind | `ifind` | ✅ 可用 | 需 `IFIND_ACCESS_TOKEN` 环境变量 |
| 腾讯财经 | `tencent` | ✅ 行情可用，K线基础实现 | 公开接口，无需鉴权 |
| 新浪财经 | `sina` | ⚠️ 行情可用，K线降级复用腾讯 | 公开接口，无需鉴权 |

切换数据源：在 `.env` 中设置 `DEFAULT_SOURCE=tencent`（或其他标识）。

---

## 环境变量配置

```env
# 行情专用 Redis（主力数据源）
REMOTE_QUOTE_REDIS_HOST=quantmind-market-redis
REMOTE_QUOTE_REDIS_PORT=6379
REMOTE_QUOTE_REDIS_PASSWORD=<password>

# 兼容旧环境变量名（可选，不建议新增使用）
# REDIS_MARKET_HOST=<host>
# REDIS_MARKET_PORT=6379
# REDIS_MARKET_PASSWORD=<password>

# 本地 Redis（行情缓存，TTL=1s）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<password>

# 数据源选择（可选，默认 remote_redis）
DEFAULT_SOURCE=remote_redis

# 同花顺 iFind（可选）
IFIND_ACCESS_TOKEN=<token>

# quotes 自动清理（仅保留当天数据）
QUOTE_CLEANUP_ENABLED=true
QUOTE_CLEANUP_KEEP_TODAY_ONLY=true
QUOTE_CLEANUP_INTERVAL_SECONDS=600
QUOTE_DAILY_ARCHIVE_ENABLED=true

# 浏览器跨域白名单（生产必配）
CORS_ALLOWED_ORIGINS=https://app.quantmind.example.com,https://quantmind.example.com
```

说明：
- `REDIS_HOST/REDIS_PORT/REDIS_PASSWORD` 用于 `TradePusher` / `NotificationPusher` 事件流消费；
  `REMOTE_QUOTE_REDIS_*` 用于行情快照拉取。两者职责不同，避免混用。
- 配置解析优先级：`REDIS_*` 高于 `REDIS_MARKET_*`（兼容字段仅作兜底）。
- `QUOTE_CLEANUP_ENABLED=true` 时，`quantmind-stream` 启动后会拉起后台任务。
- 默认先归档再清理：将 `quotes` 历史数据聚合写入 `quote_daily_summaries`（`trade_date + symbol + data_source` 唯一），然后执行清理。
- 清理规则：`DELETE FROM quotes WHERE timestamp::date < CURRENT_DATE`（按数据库日期口径，仅保留当天）。
- `QUOTE_DAILY_ARCHIVE_ENABLED=false` 时跳过归档，仅执行清理（不建议）。
- `QUOTE_CLEANUP_INTERVAL_SECONDS` 最小 60 秒，默认 600 秒。

## 数据库迁移（quotes 时区）

- 2026-03-20 起，`quotes.timestamp` 统一为 `timestamptz`，并以 UTC aware 时间写入。
- 对存量库执行：

```bash
psql "$DATABASE_URL" -f backend/db/migrations/20260320_alter_quotes_timestamp_to_timestamptz.sql
```

---

## API 端点

### REST

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/quotes/{symbol}` | 获取单只行情（支持 `?source=` 切换数据源）|
| GET | `/api/v1/klines/{symbol}` | 获取 K 线（`?interval=1d&limit=100`）|
| GET | `/api/v1/symbols` | 获取全市场标的列表 |
| POST | `/api/v1/internal/bridge/order` | 内部接口：向在线 QMT Agent 派发下单消息（需 `X-Internal-Call`） |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标（含降级状态） |

### 告警处置（P3-8）

- `StreamServiceDegraded`（warning，2m）：
  - 含义：服务存活但进入降级模式（通常是 market_db 初始化失败）。
  - 先检查：`/health` 的 `market_db` 字段与 `stream_service_degraded` 指标。
- `StreamMarketDBDisconnected`（critical，5m）：
  - 含义：市场库持续断连，可能影响行情 API 数据完整性。
  - 先检查：数据库连通性（网络、端口、凭据、实例可用性）与项目根目录 `.env` 中 `DATABASE_URL/DB_*` 配置。

### WebSocket

| 端点 | 说明 |
|------|------|
| `WS /ws` | 通用业务推送（主入口，支持行情 + 指标 + 其他业务）|
| `WS /ws/bridge` | Bridge/Agent 兼容入口（与 `/ws` 共用同一核心处理）|
| `WS /api/v1/ws/market` | 兼容旧客户端入口（由 `/ws` 同一核心处理）|

#### /ws 消息协议（统一）

```jsonc
// 客户端 → 服务器
{ "type": "subscribe",   "topic": "stock.600519.SH" }
{ "type": "subscribe",   "topic": "notification.1001" }
{ "type": "unsubscribe", "topic": "stock.600519.SH" }
{ "type": "ping" }

// 兼容旧客户端（/api/v1/ws/market）也可继续使用
{ "action": "subscribe",   "symbols": ["600519.SH"] }
{ "action": "unsubscribe", "symbols": ["600519.SH"] }
{ "action": "ping" }

// 服务器 → 客户端
{ "type": "welcome",     "connection_id": "uuid", "tenant_id": "default", "user_id": "00000001" }
{ "type": "subscribed",  "topic": "stock.600519.SH" }
{ "type": "subscribed",  "symbols": ["600519.SH"] } // 兼容模式响应
{ "type": "quote",       "stock_code": "600519.SH", "data": { "price": 1485.3, "open": 1486.6, ... }, "timestamp": 1234567890.0 }
{ "type": "notification","data": { "id": 42, "title": "订单成交确认", "content": "...", "type": "trading", "level": "success", "action_url": "/trading", "created_at": "2026-03-10T10:00:00+00:00" } }
{ "type": "pong", "timestamp": 1234567890.0 }
```

#### WS 鉴权与多租户绑定

- 默认开启握手鉴权（`WS_AUTH_REQUIRED=true`）。
- 支持 `Authorization: Bearer <token>` 或 `?token=<jwt>`。
- 兼容内部头 `X-User-Id` + `X-Tenant-Id`。
- QMT Agent 仅支持 `Authorization: Bearer <bridge_session_token>` 或 `?token=<bridge_session_token>` 建立 `/ws/bridge` 握手；
  `qm_live_*` 不再直接用于 WebSocket 握手。
- `/ws/bridge` 会先校验短期 session token，成功后再把 `tenant_id/user_id/account_id` 绑定到连接元数据。
- 普通前端连接 `/ws` 仍使用 JWT；单独传 `X-User-Id/X-Tenant-Id` 不再视为已认证。
- 当连接断开时，`quote_pusher` 会按当前全量 topic 进行订阅重算，避免“单连接取消导致全局 symbol 误删”。

---

## 已知限制

| 限制 | 说明 |
|------|------|
| High / Low / Close | 远程 Redis 快照仅提供 `Now`（现价）和 `Open`（开盘价），高低收三字段为 `None` |
| 数据延迟 | 快照每分钟更新，非 tick 级实时数据 |
| K 线历史 | `remote_redis` 不支持历史 K 线；已补腾讯基础抓取，稳定性依赖上游公开接口 |
| 技术指标 | `indicator_pusher` 中各指标 `calculate()` 为占位符，尚未实现 |

---

## 启动 & 测试

```bash
# 启动服务
cd /path/to/quantmind
uvicorn backend.services.stream.main:app --host 0.0.0.0 --port 8003 --reload

# 运行测试
source .venv/bin/activate
pytest -q backend/services/tests/test_stream_service.py
pytest -q backend/services/tests
```

---

*最后更新：2026-03-02*
