# Electron Frontend Notes

This module calls the Qlib service directly for backtest operations.

## 跨平台支持

✅ 本项目完全支持 **Windows**、**macOS** 和 **Linux** 三大平台。

**详细文档**: 请查看 [CROSS_PLATFORM.md](./CROSS_PLATFORM.md) 获取完整的跨平台配置指南。

**快速检查**:
```bash
npm run check:platform
```

## Qlib Endpoints

- Base URL: `/api/v1/qlib`
- Run backtest: `POST /api/v1/qlib/backtest`
- Get result: `GET /api/v1/qlib/results/{backtest_id}`
- History: `GET /api/v1/qlib/history/{user_id}`
- Compare: `GET /api/v1/qlib/compare/{id1}/{id2}?user_id=...`
- Delete: `DELETE /api/v1/qlib/results/{backtest_id}?user_id=...`

## Notes

- `user_id` is required for delete and compare.
- The WebSocket endpoint is `/api/v1/ws/backtest/{backtest_id}`.
- Quick backtest sends `strategy_content` when provided; otherwise it uses the default `TopkDropout` strategy.
- Empty `symbol` uses the default Qlib universe (`csi300`).
- Strategy templates include `STRATEGY_CONFIG`, and `strategy_content` is sent when provided.
- `react-window` is pinned to v1 for `FixedSizeList` usage in the backtest history UI.
- 品牌图标仅保留给安装包与安装器资源，前端页面当前不再直接展示 logo 图形。
- 模型训练页（`/model-training`）提交到 `POST /api/v1/admin/models/run-training` 时已对齐后端契约：
  - 请求字段使用 `features/train_start/train_end/valid_start/valid_end/test_start/test_end/lgb_params/num_boost_round`；
  - 不再注入硬编码基础字段（如 `open/high/low/close/volume/amount`），仅提交用户在特征字典中勾选的字段；
  - 特征选择来源统一使用 `GET /api/v1/admin/models/feature-catalog` 返回的可用字段。
- 开发模式下 `npm run dev` 的 `dev:electron` 会先执行一次 `build:electron`，确保 `dist-electron` 与源码（含 AI-IDE 端口配置）一致，避免加载到旧编译产物。
- `build:electron` 的图标复制已改为 Node `fs.copyFileSync`，避免 Windows `copy` 命令导致 macOS/Linux 下 `npm run dev` 启动失败。
- Windows 自动更新发布脚本：
  - `npm run build:package:win`：生成 Windows 安装包与更新元数据（不自动发布）
  - `npm run build:package:win:publish`：生成并按 `electron-builder publish` 规则发布
- Windows 更新服务端文件要求（generic provider）：
  - 必须上传 `latest.yml`、`*.exe`、`*.exe.blockmap`
  - 客户端会从更新源根路径读取 `latest.yml`（macOS 对应 `latest-mac.yml`）
- 更新源环境变量支持按平台拆分：
  - `UPDATE_SERVER_URL_WIN` / `UPDATE_SERVER_URL_MAC` / `UPDATE_SERVER_URL_LINUX`
  - 未配置时回退 `UPDATE_SERVER_URL`

## AI-IDE 页面说明

- 路由：`/ai-ide`（受保护路由）
- 关键交互：
  - 聊天区代码块支持“插入编辑器/复制”
  - 编辑器支持“发送选中代码”到对话区
- Monaco 编辑器资源（重要）：
  - `@monaco-editor/react` 默认会从 CDN（`cdn.jsdelivr.net`）拉取 Monaco 的 `vs/loader.js`，在企业网络/离线环境下容易导致编辑器区域长期停留在 `Loading...`。
  - 本项目已改为本地加载 Monaco 静态资源：通过 `scripts/copy-monaco-assets.js` 将 `node_modules/monaco-editor/min/vs` 复制到 `electron/public/monaco/vs`，并在 `electron/src/monaco/setup.ts` 中配置 `@monaco-editor/loader` 的 `paths.vs` 指向本地路径（`electron/src/main.tsx` 引入该 setup）。
- AI-IDE Python 运行环境（发布统一 core 内置）：
  - 默认目标：生产发布统一内置 core 运行时，确保 AI-IDE 开箱可用。
  - 生产启动代码：`electron/electron/services/ai_ide_service.ts`
  - 解释器解析优先级：用户手动配置 > 工作区/项目虚拟环境 > 系统 Python > 打包内置 Python（最后兜底）。
  - 内置 Python 打包路径（位于 `process.resourcesPath`）：
    - `python/<platform>-<arch>/python/`：Python runtime
    - `python/<platform>-<arch>/venv/`：内置 venv（发布包固定包含）
    - `backend/ai_ide_service/` + `backend/__init__.py`：AI-IDE 后端代码包
    - 构建脚本：`electron/scripts/prepare-ai-ide-python.js`
      - 需要在目标平台执行（macOS x64/arm64、Windows x64、Linux x64 分别构建）
      - 自动探测到 `.../bin` 目录时会自动归一化到可执行 runtime 根目录
      - 依赖清单路径兼容两种结构：
      - 新结构：`backend/services/ai_ide/requirements-core.txt` + `requirements-quant.txt`
      - 旧结构：`backend/ai_ide_service/requirements/base.txt` + `runtime.txt`
    - 发布档位：固定 `AI_IDE_PYTHON_BUNDLE_PROFILE=core`
      - `core`：安装 AI-IDE 基础依赖（可直接使用对话与执行）
    - Runtime 拷贝策略：会自动剔除源 Python 目录中的 `Lib/site-packages` 和 `__pycache__`，避免把开发机历史依赖全量带入安装包。
    - 打包阶段会强制升级内置 venv 的 `pip/setuptools/wheel` 到最新可用版本，并输出最终 `pip --version` 便于追踪。
    - 环境变量：
      - `AI_IDE_PYTHON_RUNTIME_DIR`：已解压的 Python runtime 目录（需包含 `bin/python` 或 `python.exe`）；未设置时脚本会自动探测（优先项目 `.venv`，其次系统 Python）。
      - `AI_IDE_WHEELHOUSE_DIR`：离线 wheels 目录（推荐，避免打包时联网）
      - `AI_IDE_PYTHON_TARGET`：可选，默认 `<platform>-<arch>`（如 `darwin-arm64`）
    - 命令：
      - `npm run build:package`：统一发布命令（内置 Python + core 依赖）
  - macOS 依赖安装：
    - 完整指南见 [`docs/AI_IDE_macOS_环境依赖安装指南.md`](/Users/qusong/git/quantmind/docs/AI_IDE_macOS_环境依赖安装指南.md)
    - Apple Silicon：发布包默认 `core`；`pyqlib` 当前不在 `arm64` 安装
    - Intel Mac：如需量化扩展请手工安装 `requirements-quant.txt`
  - 运行时依赖检测：
    - Electron 主进程会检测 `fastapi/uvicorn/pydantic/httpx/python-dotenv` 是否可用。
    - 若用户环境被手动改动导致依赖缺失，AI-IDE 设置页会显示缺失项并提供可复制安装命令（core/full）。
- 依赖的后端接口（需由服务提供）：
  - `GET /api/v1/files/list`
  - `GET /api/v1/files/list?path=<relative>`
  - `POST /api/v1/files/set-root`
  - `GET /api/v1/files/{name}`
  - `POST /api/v1/files/{name}`
  - `POST /api/v1/files/create/file`
  - `POST /api/v1/files/create/folder`
  - `POST /api/v1/files/rename`
  - `DELETE /api/v1/files/{name}`
  - `POST /api/v1/execute/start`
  - `GET /api/v1/execute/logs/{job_id}`
  - `POST /api/v1/execute/stop/{job_id}`
  - `POST /api/v1/ai/chat`
- 打包运行说明：
  - AI-IDE 后端随 Electron 一起打包，运行时由主进程预热启动（`app.whenReady` 阶段），降低首次进入 AI-IDE 的冷启动闪屏。
  - Windows 安装包已切换为 NSIS 向导安装模式（`oneClick=false`），保留“默认用户目录安装 + 无需管理员 + 不可改安装目录”，以支持更完整品牌过渡页面。
  - `npm run build:package` 现固定产出 Windows x64 NSIS 安装包（`--win nsis --x64`），避免混出 portable 包导致安装入口不统一。
  - 安装视觉资源位于 `build/`：`installerSplash.png`（安装前品牌图）、`installerHeader.png`、`installerSidebar.png`。替换同名文件即可更新安装器视觉。
  - Windows NSIS 安装阶段会自动创建安装目录下的 `domocode` 默认工作区（`$INSTDIR\\domocode`）。
  - 生产环境策略目录使用用户数据目录：`<userData>/ai_ide/strategies`（可写）
  - 生产环境历史数据目录：`<userData>/ai_ide/data`
  - 可通过环境变量覆盖：`AI_IDE_PROJECT_ROOT`、`AI_IDE_STRATEGY_DIR`
  - 前端支持选择本地工作目录（IPC: `ai-ide:select-directory`）
  - 前端读取/保存/删除使用路径编码，避免包含子目录的文件加载失败
- Windows 打包优化（2026-03）：
  - 新增 `npm run build:package:win`：Windows 专用打包入口（`--win --x64`，默认产出安装包）。
  - 新增 `npm run build:package:win:dir`：仅生成目录产物（不出安装包），用于快速验证。
  - `electron-builder` 默认关闭依赖重建：`npmRebuild=false`、`nodeGypRebuild=false`、`buildDependenciesFromSource=false`，减少 Windows 打包阶段的本地重建风险。
  - NSIS 使用 electron-builder 默认模板（用户级安装，默认安装到用户目录），不再依赖额外动画/启动图片资源。
  - Windows 安装器图标固定引用 `../tools/qmt_agent/icon.ico`，避免依赖 `electron/build` 下的本地图标资源。
- 创建文件/文件夹使用自定义弹窗（不依赖 `prompt()`）
- 创建失败时会展示后端返回的详细错误信息
- 当模型未返回代码块时，前端会基于内容特征自动包裹为代码块展示
- AI 对话渲染使用 Markdown 解析（支持代码块按钮与更稳定的流式渲染）
- 流式期间仅显示文本，完成后再进行代码块包裹与渲染，避免空代码块闪烁
- 流式过程中不渲染 Markdown 代码块，避免半截 fenced code 导致的空块
- 支持用 `#代码开始` / `#代码结束` 标记提取并渲染代码
- 前端支持基于 `#代码开始` / `#代码结束` 的流式代码块分段渲染
- SSE 支持结构化 JSON 事件（`{type: "text" | "code", delta: "..."}`），用于更稳定的流式分段
- **UI/UX 增强 (v2.0)**:
  - **智能代码块识别**: 支持混合 Token Scanning，能够实时解析流式传输中的 Markdown 代码围栏（\`\`\`）和 Diff 标记（<<<< SEARCH），确保未闭合的代码块也能立即渲染，杜绝“裸代码”显示。
  - **增强的 Diff 视图**: 
    - 采用流式 Diff 解析器，支持 `LOADING_SEARCH` / `LOADING_REPLACE` 状态，平滑展示 AI 生成过程。
    - 优化了 Diff 块布局，对内容添加了 `min-w-0` 约束，防止长代码撑破容器，并正确触发内部水平滚动条。
  - **代码阅读体验**:
    - 全面引入 PrismJS 语法高亮，支持 Python/Bash/JSON 等多种语言。
    - 优化代码字体颜色（深色高对比度）和排版，提升阅读舒适度。
    - 强制文本自动换行（`break-words` + `whitespace-pre-wrap`），修复了中文/长文本被容器截断的问题。
  - **布局优化**:
    - 移除了页面级水平滚动条，将滚动限制在代码块内部。
    - 优化了 Chat Bubble 的宽度约束和 Flex 布局，确保在各种窗口尺寸下都能完美展示。
  - **AI 指令优化**: 更新了 System Prompt，强制 AI 使用标准 Markdown 格式输出代码，从源头进一步保障显示效果。

## 本地联调用户服务（端口 8002）

- 确保 `electron/.env` 指向 8002 端口：
  ```env
  VITE_USER_API_URL=http://127.0.0.1:8000/api/v1
  VITE_USER_CENTER_API_URL=http://127.0.0.1:8000/api/v1
  VITE_TENCENT_COS_URL=https://cos.quantmind.cloud
  ```
- 如果自定义端口，请保持 `.env` 与后端端口一致，修改后需重启前端开发服务器。
- 用户中心头像展示域名支持在“个人中心 -> 其他设置”可视化配置（本地存储键：`user_center_avatar_cos_domain`）；上传返回仅含 `file_key` 或无路径 URL 时，前端会自动拼接为 `{COS域名}/{file_key}`。
- 前端会自动去除 `VITE_*_API_URL` 末尾的 `/api/v1`，避免重复拼接导致 404。
- 头像上传失败时，若后端返回业务错误码（`code != 0/200`），前端会优先展示后端原始 `message`，用于快速定位 COS 配置/权限/路由问题。
- 社区发帖媒体上传（图片/视频/附件）已改为真实调用网关 `POST /api/v1/files/upload`，并使用 `onUploadProgress` 展示真实上传进度。
- 策略社区联调（P0）：
  - Electron 默认通过 API Gateway（8000）访问社区：`/api/v1/community/*`
  - `VITE_USE_MOCK_COMMUNITY=true` 可强制使用前端 Mock（默认关闭，走真实后端链路）
  - 评论点赞当前未实现，UI 已隐藏（避免误调用 `posts/{id}/like`）
  - 多租户（P1）：`electron/src/services/api-client.ts` 会自动附加 `X-Tenant-Id` 请求头（优先读取已登录用户的 `tenant_id`，否则读取 `VITE_TENANT_ID`，默认 `default`）。
- 实盘/模拟盘启动前自检弹窗：
  - 前端统一调用 `GET /api/v1/real-trading/preflight`。
  - `SIMULATION` 模式也会弹出“启动前自检详情”明细窗口；若存在必需项失败则阻断启动。
- 模拟盘在弹窗内点击“确认并启动模拟盘”后才会真正发起 `/start`，避免自检通过即自动启动。
- 管理后台“生成明日信号”前置检查（`/admin/models/precheck-inference`）已改为前端分级门禁：
  - 阻断项（必须通过）默认仅包括：生产模型目录、模型文件、metadata、推理脚本可用性、`market_data_daily` 查询可用性。
  - 其余数据就绪类检查改为提醒项（不阻断执行），并在弹窗中默认折叠通过项，只展示关键项与失败项，支持“展开全部检查”。

## Electron 联调正式后端（kubectl port-forward）

- 适用场景：Electron 前端需要直接联调当前 `quantmind-prod` 集群后端，但暂时不通过公网 Ingress。
- 本地转发端口约定：
  - `http://127.0.0.1:18000` -> `quantmind-api`
  - `http://127.0.0.1:18001` -> `quantmind-engine`
  - `http://127.0.0.1:18002` -> `quantmind-trade`
  - `http://127.0.0.1:18003` -> `quantmind-stream`
  - `ws://127.0.0.1:18003/api/v1/ws/market` -> 行情 WebSocket
- 推荐在 `electron/.env.local` 中覆盖以下变量：
  ```env
  VITE_API_URL=http://127.0.0.1:18000
  VITE_API_BASE_URL=http://127.0.0.1:18000
  VITE_API_GATEWAY_URL=http://127.0.0.1:18000
  VITE_DATA_SERVICE_API_URL=http://127.0.0.1:18000
  VITE_USER_API_URL=http://127.0.0.1:18000/api/v1
  VITE_TRADING_API_URL=http://127.0.0.1:18002
  VITE_REAL_TRADING_API_URL=http://127.0.0.1:18002
  VITE_QLIB_SERVICE_URL=http://127.0.0.1:18001
  VITE_AI_STRATEGY_API_URL=http://127.0.0.1:18001
  VITE_STOCK_QUERY_API_URL=http://127.0.0.1:18001
  VITE_MARKET_DATA_API_URL=http://127.0.0.1:18003
  VITE_STREAM_SERVICE_URL=http://127.0.0.1:18003
  VITE_WEBSOCKET_MARKET_URL=ws://127.0.0.1:18003/api/v1/ws/market
  ```
- 说明：
  - `AuthService` 会保留 `VITE_USER_API_URL` 里的路径前缀，因此这里必须显式写成 `/api/v1`。
  - 其它 `VITE_*_API_URL` 经过统一服务配置归一化后会自动补 `/api/v1`，不需要重复追加。
- `electron/.env.local` 已被 `.gitignore` 忽略，适合本机联调，不会污染仓库默认配置。
- 启动 Electron 前请确保本机 `kubectl port-forward` 仍在运行；如果转发会话中断，上述端口会立即失效。

## ESLint 增量与分阶段治理

- 增量门禁（推荐先接 CI）：
  - `npm run lint:changed`
  - 仅检查当前 Git 变更的 `src/**/*.ts(x)` 文件，避免被历史存量问题阻塞。
- 分阶段清债：
  - `npm run lint:phase1`（`pages/services/config/constants/contexts/providers`）
  - `npm run lint:phase2`（`features/store/stores/state`）
  - `npm run lint:phase3`（`components/hooks/shared/types/utils/i18n/main/monaco`）
- 查看阶段目标（不执行 lint）：
  - `npm run lint:phase -- --phase=1 --list`

## 短信验证码登录 + 个人中心绑定/换绑手机号（阿里云短信）

- 发送登录验证码（未登录）：
  - `POST /api/v1/sms/send`，body: `{ phone, tenant_id, type: "login" }`
- 短信验证码登录：
  - `POST /api/v1/auth/login/phone`，body: `{ phone, code, tenant_id }`
- 个人中心绑定/换绑（需登录）：
  - `POST /api/v1/users/me/phone/send-code`，body: `{ purpose: "bind_phone" | "change_phone_old" | "change_phone_new", phone? }`
  - `POST /api/v1/users/me/phone/bind`，body: `{ phone, code }`
  - `POST /api/v1/users/me/phone/change`，body: `{ old_code, new_phone, new_code }`

说明：Electron 默认通过 API Gateway（8000）访问上述路径，由网关转发到 `user_service`。

## AI-IDE 根目录说明

- AI-IDE 后端运行在容器内时，前端会将本机路径自动映射到容器路径：
  - 本机：`/Users/qusong/...`
  - 容器：`/app/host/...`
  - 本机项目目录：`/Users/qusong/git/quantmind/...`
  - 容器项目目录：`/app/quantmind/...`
- 如需手动输入根目录，请使用容器路径（例如 `/app/host` 或 `/app/quantmind`）。

## 认证刷新重试策略

- 前端对 401 触发的令牌刷新最多自动重试 2 次，连续失败会清空本地令牌并停止重复弹错；30 秒后重试计数自动归零。
- 刷新接口（`/auth/refresh` / `/refresh`）返回 401 时不会再触发二次刷新，避免刷新风暴；此时直接清理本地令牌并由认证守卫处理跳转。
- 登录/注册成功后会在认证 thunk 内再次写入本地令牌与用户信息，作为冗余保障，避免局部存储写入异常导致登录态丢失。
- 登录态判断以 `access_token` 为准，即使 `user` 尚未加载也不会直接退出，初始化会尝试拉取 `/users/me` 补全用户信息。
- 如遇异常退出登录，开发模式下会在控制台输出 `clearTokens` 调用栈和用户中心 401 请求信息，便于定位清理原因。

## 个人中心数据读取策略

- 个人中心不再使用本地缓存（profile/config），所有信息均实时从后端读取。
- 用户中心接口返回 401 时不再尝试刷新令牌，直接清理本地凭据并交由认证守卫处理跳转。

## WebSocket 调试开关

- 设置 `VITE_DISABLE_WEBSOCKET=true` 可禁用全局 WebSocket 自动连接（用于调试登录问题）。
- 登录页仅在 `VITE_DISABLE_AUTH=true` 时执行一次自动登录，避免默认开发模式下请求失败造成的持续报错。
- Windows 圆角渲染修复：`platform-win32` 下禁用 Web 层 `html/body/#root/.app-root` 二次圆角裁剪，仅保留系统原生窗口圆角，避免登录页角落露出白底。
- 启动体验优化：认证初始化阶段若本地无令牌（或当前在 `/auth/*` 公共路由）时，`App` 不再渲染 `DashboardSkeleton`，改为登录风格渐变 + `Spin` 启动态，减少启动时“蓝底闪屏”。
- 首屏无 JS 兜底：`electron/index.html` 内联了启动渐变背景与轻量 loading，占位会在 React 挂载后自动被替换，避免 bundle 加载前出现纯色背景。
- 主窗口显示时机优化：`BrowserWindow` 使用 `show: false` + `ready-to-show` 后再显示，减少启动阶段系统底色闪现。
- 启动无蓝底优化：主窗口改为 `ready-to-show` 与 `did-finish-load` 双条件满足后再显示，并将窗口兜底色从深蓝调整为中性深灰，进一步降低启动前蓝底可见概率。

## 策略向导智能解析

- 智能解析调用 `/strategy/parse-text` 可能触发 AI Strategy 预热与 LLM 推理，前端请求超时已提升到 120s。
- 若在“风格选择”点击下一步时未检测到股票池文件，前端会自动保存当前股票池并再触发生成流程。
- 仓位管理启用“动态仓位调整”后，市场环境检测设置不再展示，策略总仓位占比滑条会锁定。
