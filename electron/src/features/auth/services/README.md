# services

用途：服务层与数据访问逻辑。

## 说明
- 归属路径：electron\src\features\auth\services
- 修改本目录代码后请同步更新本 README
- `authService.getCurrentUser()` 支持 `suppressUnauthorizedLog` 选项，供初始化阶段静默处理 `/api/v1/users/me` 的 401，避免未登录态把鉴权失效打印成前端错误。
