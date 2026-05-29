# pages

用途：页面与路由视图。

## 说明
- 归属路径：electron\src\features\user-center\pages
- 修改本目录代码后请同步更新本 README

## 策略页字段对齐（2026-02-20）

- `StrategiesPage` 策略名称列已对齐使用 `name` 字段，并兼容 `strategy_name` 回退读取，避免列表名称空白。

## 个人中心 Tab 容器对齐（2026-03-09）

- `UserCenterPage` 为 `个人档案/安全设置/我的策略/其他设置` 四个 Tab 统一增加同一层内容容器（固定 `min-height`），消除切换时内容区域起始位置位移。
- `UserCenterPage` 在 Tab 切换时统一重置内容滚动到顶部，并为滚动容器启用 `scrollbar-gutter: stable`，避免“我的策略”因滚动条出现导致轻微横向位移。
