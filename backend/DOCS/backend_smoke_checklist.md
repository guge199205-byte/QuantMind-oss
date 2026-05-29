# 后端四服务 Smoke 检查清单

适用范围：`quantmind-api`、`quantmind-engine`、`quantmind-trade`、`quantmind-stream` 在预发、灰度、正式发布前的最小联调检查。

## 执行前提

- 已完成数据库 migration 与必要 bootstrap。
- 根目录 `.env` 已配置：
  - `INTERNAL_CALL_SECRET`
  - `SECRET_KEY`
  - `DATABASE_URL` 或等效 `DB_*`
  - `REDIS_*`
  - 生产/预发浏览器场景下的 `CORS_ALLOWED_ORIGINS`
- 四个服务均已启动：
  - `quantmind-api` : `8000`
  - `quantmind-engine` : `8001`
  - `quantmind-trade` : `8002`
  - `quantmind-stream` : `8003`

## 1. 健康检查

逐个检查：

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8002/health
curl -s http://127.0.0.1:8003/health
```

通过标准：
- 四个接口都返回 `200`
- `status` 为 `healthy` 或明确可接受的 `degraded`
- `service` 字段分别匹配服务名

## 2. 指标暴露

```bash
curl -s http://127.0.0.1:8000/metrics | rg "quantmind_service_health_status"
curl -s http://127.0.0.1:8001/metrics | rg "quantmind_service_health_status"
curl -s http://127.0.0.1:8002/metrics | rg "quantmind_service_health_status"
curl -s http://127.0.0.1:8003/metrics | rg "quantmind_service_health_status|stream_market_db_connected"
```

通过标准：
- 四个服务都能返回指标文本
- 指标中包含对应 `service` 标签

## 3. CORS 校验

开发环境示例：

```bash
curl -i -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login \
  -H "Origin: http://127.0.0.1:3000" \
  -H "Access-Control-Request-Method: POST"
```

生产/预发示例：

```bash
curl -i -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login \
  -H "Origin: https://app.quantmind.example.com" \
  -H "Access-Control-Request-Method: POST"
```

通过标准：
- 已配置白名单的域名返回正确 `access-control-allow-origin`
- 未配置域名不返回放行头
- 生产环境不允许 `*`

## 4. API -> Engine 代理

```bash
curl -i http://127.0.0.1:8000/api/v1/strategies
```

通过标准：
- 未登录请求返回受控错误（通常 `401`），而不是网关 `500`
- 已登录情况下能正确透传到 `engine`

## 5. API -> Trade 代理

```bash
curl -i http://127.0.0.1:8000/api/v1/orders
```

通过标准：
- 未登录请求返回 `401/403/422` 等受控鉴权错误
- 不出现 `502/503/504` 的代理故障

## 6. 内部密钥联通

使用同一个 `INTERNAL_CALL_SECRET` 验证 `engine` 内部路由：

```bash
curl -i http://127.0.0.1:8001/api/v1/nonexistent_endpoint_xyz \
  -H "X-Internal-Call: ${INTERNAL_CALL_SECRET}"
```

通过标准：
- 返回 `404`，说明内部密钥通过且请求进入业务路由层
- 若返回 `401`，优先排查服务间密钥不一致

## 7. Stream WebSocket

连接：

```bash
wscat -c "ws://127.0.0.1:8003/ws?token=<jwt>"
```

订阅：

```json
{"type":"subscribe","topic":"stock.600519.SH"}
```

通过标准：
- 成功建立连接
- 收到 `welcome`
- 订阅后收到 `subscribed`
- 有行情时能收到 `quote`

## 8. 日志与请求 ID

检查四个服务日志：

- 是否包含 `request_id`
- 是否包含 `service`
- 代理调用链前后 `request_id` 可关联

## 9. 最小回归

```bash
source .venv/bin/activate
pytest -q backend/services/tests/test_api_service.py
pytest -q backend/services/tests/test_engine_service.py
pytest -q backend/services/tests/test_trade_service.py
pytest -q backend/services/tests/test_stream_service.py
```

通过标准：
- 四组基础测试全部通过

## 发布阻断条件

以下任一命中即阻断发布：

- 任一服务 `/health` 不可用
- 任一服务 `/metrics` 缺失
- `INTERNAL_CALL_SECRET` 不一致导致跨服务 401
- 生产环境 CORS 仍为 `*`
- `api -> engine` 或 `api -> trade` 代理出现 5xx
- `stream` WebSocket 无法握手或订阅
