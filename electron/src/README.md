# src

用途：与 src 相关的前端实现。

## 说明
- 归属路径：electron\src
- 修改本目录代码后请同步更新本 README
- 用户中心档案接口统一使用 `GET/PUT /api/v1/profiles/me/profile`，避免依赖前端硬编码用户 ID。
- 个人档案表单在只读模式下保持“编辑档案”按钮可点击，字段默认回填认证用户的 `username/email`。
- 策略向导 Step3 仓位管理会调用 `GET /api/v1/strategy/market-state` 获取实时市场状态。
- 策略向导 Step3 同时调用 `POST /api/v1/strategy/validate-position` 做动态仓位校验与持仓估算。
- 策略向导 Step4 风格选择调用 `POST /api/v1/strategy/apply-style` 统一后端风格映射。
- Step4 点击“下一步”触发 `generate-qlib` 时会弹出阻塞提示窗口，提示生成耗时约 1-2 分钟；生成完成后自动关闭并进入下一步。
- 策略向导 Step5 保存策略调用 `POST /api/v1/strategy/save-to-cloud`，并落库到 `user_strategies`。
- 策略向导 Step2 会保存股票池为 TXT（QLib instruments 格式，如 `SZ000001`）并上传 `save-pool-file`，Step4 点击右上角“下一步”触发 `generate-qlib`。
- `generate-qlib` 请求仅传递 `pool_file_key`（更安全，避免暴露直链），并将前端超时时间设置为 2 分钟以适配大模型生成时延。
- Step5 校验仅做语法检查，调用 `validate-qlib` 时传 `mode=syntax_only`。
- 若未在 Step5 保存策略，离开页面会调用 `delete-pool-file` 清理股票池文件。
- AI-IDE 远程策略页签通过 `GET /api/v1/remote/strategies` 拉取策略列表，点击后调用 `GET /api/v1/remote/strategies/{id}` 加载代码，远程策略为只读。
- AI-IDE 页面在 Electron 运行时默认优先直连 `VITE_AI_IDE_DIRECT_BASE_URL`（默认 `http://127.0.0.1:8010/api/v1`）；若先走网关时 AI-IDE 核心接口返回 `401/403/404/5xx` 或网络失败，也会自动回退到本机直连；请求统一附带 `Authorization` 与 `X-Tenant-Id`。
- `main.tsx` 已改为“应用启动即触发” `preloadAiIdeResources`（不等待登录页/路由），并联动预热 Monaco/Prism 与 `monaco/vs` 关键静态资源，降低 AI-IDE 首次加载闪烁与等待。
- `App.tsx` 现已在应用启动后立即预加载 AI-IDE 资源，并在空闲阶段再补一次预热，减少首次进入 `/ai-ide` 的白屏与延迟。
- `App.tsx` 新增 AI-IDE 保活机制：每 30 秒调用一次 `keepAliveAIIDEBackend`，若本地后端未运行会自动拉起，降低 `127.0.0.1:8010` 冷启动拒连概率。
- `AIIDEPage.tsx` 的后端就绪等待改为优先走主进程 IPC（`waitAIIDEBackendReady`）轮询端口，不再默认由渲染层直接探测 `127.0.0.1:8010`，降低控制台 `ERR_CONNECTION_REFUSED` 噪音。
- AI-IDE 的 Python 检测逻辑已优先识别打包内置 Python runtime（且 core 依赖就绪），即使系统未安装 Python 也不会误报“未安装/未配置环境变量”。
- `styles/global.css` 新增 Monaco 初始化兜底样式：强制隐藏 `.monaco-editor textarea.inputarea`，避免编辑器样式尚未加载时出现短暂的原生输入框闪现。
- `styles/global.css` 增加 `body/#root` 顶层圆角裁剪，强化不同 Windows 机器上的全局圆角一致性。
- 回测中心“高级分析”里的“选择回测结果”已从原生 `<select>` 改为 `antd Select`，下拉弹层可统一应用圆角与阴影样式。
- `electron.d.ts` 已补齐 AI-IDE IPC 类型：`checkPython/getAIIDEConfig/updateAIIDEConfig/selectPython`，避免 `window.electronAPI` 类型缺失导致的编译错误。
- `electron.d.ts` 新增 `ensureDefaultAIIDEWorkspace` IPC 类型，用于 AI-IDE 首次启动时初始化默认 `domocode` 工作区。
- 开发模式下会优先直连 `VITE_AI_IDE_DIRECT_BASE_URL`，避免本地 Electron/Vite 联调时先命中网关再报一轮 `503 ai_ide upstream unavailable`。
- 主界面窗口圆角策略已统一：渲染层根容器固定 `16px` 圆角并裁剪，移除 Windows 透明背景特判，配合主进程非透明窗口实现跨平台一致外观。
- 主界面窗口圆角策略已统一：渲染层根容器固定 `16px` 圆角并裁剪，移除 Windows 透明背景特判，配合主进程非透明窗口实现跨平台一致外观。
- 策略向导模板接口统一通过 API Gateway 请求 `/api/v1/strategies/templates`，不再直连 engine，避免触发内部鉴权。
- AI-IDE 聊天请求仅使用当前登录用户身份（`user_id/id/username`），不再回退固定默认用户 ID。
- AI-IDE 操作交互（删除、重命名、命名输入、错误提示）统一使用 antd `Modal/message`，避免浏览器原生 `alert/prompt/confirm`。
- Python 环境缺失提醒已从“登录后全局提示”调整为“仅进入 `/ai-ide` 时提示”，避免在非 AI-IDE 页面干扰用户。
- 悬浮导航与 App 已移除调试日志，且不再对 `community` 执行无对应路由的物理跳转。
- 回测中心个人策略管理改为统一走网关 `GET/POST/DELETE /api/v1/strategies`，不再使用前端 `localStorage` 作为主存储。
- 回测中心 `StrategyManagementModule` 已移除前端 `mockStrategies`，列表与删除均直连网关策略接口并透传登录态。
- 回测中心“深度学习时序策略”模板的 `signal` 统一改为 `<PRED>`，由后端按 `QLIB_PRED_PATH` 解析默认预测文件，避免前端硬编码模型文件路径。
- 个人中心策略详情页改为通过 `userCenterService` 访问统一策略接口，不再直连 `http://localhost:8011`。
- antd v5 起 `Card.bodyStyle` 已弃用，统一改为 `styles={{ body: ... }}`。
- 智能图表模块已增加响应兼容归一化：当网关返回 `{data: ...}` 对象而非数组时，`useIntelligenceCharts` 会先转换为数组；`chartOptions` 也增加非数组保护，避免 `data.filter is not a function`。
