# services

用途：服务层与数据访问逻辑。

## 说明
- 归属路径：electron\src\features\strategy-wizard\services
- `wizardService.generateQlib` 采用异步任务轮询：`POST /strategy/generate-qlib/async` + `GET /strategy/generate-qlib/tasks/{task_id}`，以规避同步长请求导致的网关 `504`。
- `generateQlib` 的 `qlib_params` 已兼容 `rebalance_days`（1/3/5）与历史 `rebalance_period` 并存，优先使用 `rebalance_days`。
- `wizardService.searchStocks` 已切换为通过后端网关 `GET /api/v1/stocks/search` 查询（不再浏览器直连腾讯域名），从根源规避本地开发环境 `127.0.0.1:3000` 的 CORS 拦截；并兼容 `results/data` 两种响应结构映射到前端 `{symbol,name}`。
- `strategyTemplateService.getTemplates` 现统一携带 `Authorization` 与 `X-Tenant-Id` 请求头访问 `GET /api/v1/strategies/templates`，并复用 `authService.handle401Error` 执行 token 刷新与单次重试，避免模板加载因未鉴权直接 `401`。
- 修改本目录代码后请同步更新本 README
