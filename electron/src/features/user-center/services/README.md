# services

用途：服务层与数据访问逻辑。

## 说明
- 归属路径：electron\src\features\user-center\services
- 修改本目录代码后请同步更新本 README

## 头像 URL 域名归一化

- `userCenterService` 会对头像 URL 做域名归一化：
  - `*.cos.*.myqcloud.com` 与网关本地上传地址会统一转换到自定义 COS 域名。
- 自定义域名来源优先级：
  1. 用户中心“其他设置”中保存的本地配置（`localStorage` 键：`user_center_avatar_cos_domain`）
  2. 环境变量 `TENCENT_COS_URL` / `VITE_TENCENT_COS_URL`
  3. 默认值 `https://cos.quantmind.cloud`

## 策略列表接口兼容（2026-02-20）

- `userCenterService.getUserStrategies` 现兼容后端返回的 `strategies/items/list/array` 多种列表字段。
- `status` 在映射时统一转为小写，避免前端状态筛选与展示因大小写不一致失效。

## 错误信息透传增强（2026-03-03）

- `userCenterService` 的错误处理已支持解析网关统一错误结构：
  - `error.message`
  - `message`
  - `detail`（字符串与 FastAPI 校验数组）
- 用户中心调用失败时，会优先显示后端真实错误原因（如“旧密码错误”“密码需包含至少一个大写字母”），不再只显示泛化状态码错误。
