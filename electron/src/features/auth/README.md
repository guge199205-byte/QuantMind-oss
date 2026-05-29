# auth

用途：认证与登录相关功能。

## 说明
- 归属路径：electron\src\features\auth
- 修改本目录代码后请同步更新本 README

## 多租户（tenant_id）
- 后端 `user_service` 登录/注册接口要求 `tenant_id` 为必填字段。
- 前端采用最小改动方案：未在表单中显式输入时，默认使用 `VITE_TENANT_ID`；若未配置则回退为 `default`。
- 建议在根目录 `.env` 增加（示例）：
  - `VITE_TENANT_ID=default`

## 令牌刷新与 QuantBot 协同
- `authService` 提供并发安全的刷新流程（`getRefreshedToken`），同一时刻仅触发一次刷新请求，避免刷新风暴。
- QuantBot 请求链路会在发送前主动检查 access token 是否过期；过期时尝试静默刷新，刷新失败时清理本地认证信息并要求重新登录。
- 页面侧会等待 `auth.isInitialized && auth.isAuthenticated` 后再发起 QuantBot 的会话/消息请求，减少认证初始化窗口导致的 401 干扰日志。

## 初始化探活
- `initializeAuth` 调用 `getCurrentUser({ suppressUnauthorizedLog: true })`，在本地 token 失效或未登录时静默处理 `/api/v1/users/me` 的 401。
- 这样可以避免页面首次加载时把“预期中的鉴权失效”打印成前端错误，同时仍保留登录、刷新与其他接口的异常告警。

## 注册（手机号为必填，邮箱可选）
- 注册流程默认使用“手机号 + 短信验证码”注册（阿里云短信），后端会自动生成用户名。
- 发送注册短信验证码：`POST /api/v1/sms/send`，body: `{ phone, tenant_id, type: "register" }`
- 提交注册：`POST /api/v1/auth/register/phone`，body: `{ phone, code, password, tenant_id }`
- 邮箱字段在 UI 为可选项；当前版本不强制写入后端用户表（如需写入，需要后端提供“绑定邮箱/修改邮箱”接口）。
