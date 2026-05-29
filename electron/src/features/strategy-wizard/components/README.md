# components (V2)

用途：智能策略向导版本的可复用 UI 组件与核心界面逻辑。

## 说明
- 归属路径：`electron/src/features/strategy-wizard/components`
- V2 版本基于 V1 的专业左右分栏布局与底部状态栏进行了重构，视觉和交互对标企业级专业体验。
- 采用 Zustand 进行统一的状态管理（`useWizardV2Store`），实现了 WorkingPool（走 Redis 缓存）与 SavedPool/ActivePool（走 PG + COS）的读写分离与架构隔离。
- 修改本目录代码后请同步更新本 README。

## 第一步：条件选股与构建资产库

- **核心入口**: `NaturalTextInput.tsx`，整合了“自然语言描述”、“简易构建器”、“股票池管理”三大板块，已全局压缩高度和内边距，减少无效空白，提升屏效。
- **左右分栏选择器**: `CustomStockSelector.tsx` 整合了 `StockPoolLibrary.tsx`（左侧侧边资产库）与 `StockPoolTable.tsx`（右侧表格）。
- **资产库复用与加载优化**：
  - 在 `StockPoolLibrary.tsx` 中点击左侧历史股票池复用时，不再由前端发起冗余的特征查询，直接复用后端 `/preview-pool-file` 中查表返回的 `stock_daily_latest` 数据，实现“秒切”。
  - 左侧凭证鉴权统一采用 `getWizardUserId()`，解决部分情况下 `localStorage.user_id` 未更新导致请求落到 `default_user` 的鉴权失败与拉取空白问题。
- **本地股票导入与表格优化**：
  - `StockPoolTable.tsx`：底层表格移除了冗余截断，接入 Antd 分页（默认 pageSize: 10），更好地承载成百上千只标的。
  - 用户从本地上传 CSV 导入股票时，彻底修复了之前的**网络风暴漏洞**（原循环触发 `addWorkingPoolItem` 导致大量并发写入 Redis），改为本地计算增量并单次批量提交。
  - 对于用户自行上传的无表头极简 CSV，默认 fallback 取第一列，增强了容错率。

## 第三步：策略参数（Qlib 专用）
- `SmartStrategyStudioV2.tsx` 左侧步骤提示文案明确为：`Qlib专用参数（TopK / 调仓 / 风控）`。
- `QlibParamsConfig.tsx` 的调仓周期选项与快速回测统一为：`每1天 / 每3天 / 每5天（推荐）`。
- `wizardService.generateQlib` 的 `qlib_params.n_drop` 类型改为可选，并补充 `min_score/max_weight`，与 `QlibParams` 逻辑保持一致。

## 第五步：Qlib 验证与保存
- `QlibValidatorAndSave.tsx` 包含：`语法检查`、`保存策略`
- 语法检查：调用后端 `POST /api/v1/strategy/validate-qlib`（`mode=syntax_only`）执行 AST 语法解析校验。
- AI 修复：当语法不通过时展示按钮，调用后端让大模型修复代码，并自动再次检查。
- 保存到个人中心：调用后端 `POST /api/v1/strategy/save-to-cloud`。
- 保存防抖与动画：保存期间启用请求锁（禁止重复点击保存），同时禁用关闭/取消并显示“正在保存到云端”动态提示，避免重复提交。
