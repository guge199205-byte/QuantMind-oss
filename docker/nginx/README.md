# QuantMind Gateway (Nginx)

## 说明

该目录维护 QuantMind 统一网关配置，负责将前端流量按路径转发到核心集群服务：

- `quantmind-api` (`8000`)
- `quantmind-trade` (`8002`)
- `quantmind-engine` (`8001`)
- `quantmind-stream` (`8003`)

Qlib 回测相关路径（`/api/v1/qlib/*`、`/api/v1/backtest/*`、`/api/v1/strategies/*`）现在统一先转发到 `quantmind-api`，再由 API 网关注入内部信任头后转发到 `quantmind-engine`。这样可以避免前端直连 engine 时丢失 `X-Internal-Call` 或用户上下文，导致 `401 Unauthorized`。

## 动态 DNS 防复发机制

为避免后端容器重建后 IP 变化导致网关仍访问旧 IP（表现为 `502 Bad Gateway` / 登录 CORS 预检失败），网关启用：

- `resolver 127.0.0.11 valid=10s ipv6=off`
- 变量形式 `proxy_pass`（例如 `proxy_pass $api_upstream;`）

以上组合可让 Nginx 通过 Docker DNS 周期性重新解析上游域名，降低手工重启网关的需求。

## 发布与验证

在部署机项目目录执行：

```bash
docker compose up -d --build quantmind-gateway
```

验证登录链路：

```bash
curl -i -X OPTIONS "https://api.quantmind.cloud/api/v1/auth/login" \
  -H "Origin: http://127.0.0.1:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization"
```

期望返回 `HTTP/1.1 200 OK` 且包含 `Access-Control-Allow-Origin`。
