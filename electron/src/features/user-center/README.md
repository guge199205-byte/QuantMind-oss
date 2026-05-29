# user-center

用途：用户中心模块。

## 说明
- 归属路径：electron\src\features\user-center
- 修改本目录代码后请同步更新本 README
- 个人中心相关页面/弹窗的 API 调用统一通过 `SERVICE_ENDPOINTS`（默认走 API Gateway `8000`），避免硬编码端口导致鉴权不一致。

## 手机号绑定/换绑（短信验证码）

本模块在“个人档案”页面提供手机号的绑定/换绑入口：
- 未绑定：发送 `bind_phone` 验证码并绑定手机号
- 已绑定：分别验证旧手机号验证码（`change_phone_old`）与新手机号验证码（`change_phone_new`）后完成换绑

对应后端接口（经 API Gateway 转发）：
- `POST /api/v1/users/me/phone/send-code`
- `POST /api/v1/users/me/phone/bind`
- `POST /api/v1/users/me/phone/change`

## 其他设置（模拟盘与头像域名）

- 模拟盘初始金额：支持以 10 万为步进调整，并受 30 天冷却限制。
- 头像 COS 访问域名：在“其他设置”中可视化配置，保存后会用于头像 URL 的域名归一化展示与写入。

## 头像上传链路约定（2026-02）

- 上传接口：`POST /api/v1/files/upload`（网关转发到 COS 上传服务）。
- 返回字段：前端优先读取 `data.file_url` + `data.file_key`；若仅返回 `file_key`，前端会自动拼接 `{COS域名}/{file_key}`。
- 错误处理：当后端返回 `code != 0/200` 时，前端直接透传后端 `message`，避免“未获取到文件URL”这类泛化报错。
- 本地调试：仅在应急调试时使用 `/api/v1/files/local/*`，正式链路必须走 `/api/v1/files/upload`。
