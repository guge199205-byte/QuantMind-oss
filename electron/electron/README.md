# electron

用途：与 electron 相关的前端实现。

## 说明
- 归属路径：electron\electron
- 修改本目录代码后请同步更新本 README

## AI-IDE 相关

- 新增 IPC：`ai-ide:select-directory` 用于选择本地工作目录
- 选择目录后由主进程返回路径给渲染进程
- 新增 IPC：`ai-ide:ensure-default-workspace`，会自动创建 `domocode` 默认工作区，并生成 `AI-IDE_完整依赖安装说明.md`。
- 新增 IPC：`ai-ide:restart-backend`，用于在设置页执行“一键重启 AI-IDE 后端”。
- 新增 IPC：`ai-ide:keepalive`，渲染进程可定时调用，主进程会在后端未运行时自动拉起并返回运行状态。
- 新增 IPC：`ai-ide:wait-ready`，主进程轮询本地端口就绪状态后返回，供渲染层初始化阶段等待后端可用。
- 主进程统一注册 AI-IDE IPC：`check-python/get-config/update-config/select-python/get-runtime-status/restart-backend/keepalive/wait-ready/ensure-default-workspace`，避免渲染层 `ipcRenderer.invoke` 出现 `No handler registered`。
- 生产模式加载前端页面时，主进程会按多候选路径解析 `dist-react/index.html`，兼容 `app.asar`、`resources/app` 以及历史目录结构，避免安装包内目录差异导致 `Missing index.html`。
- `ai-ide:ensure-default-workspace` 现会按平台生成独立文件：
  - Windows: `AI-IDE_完整依赖安装说明_Windows.md`
  - macOS: `AI-IDE_完整依赖安装说明_macOS.md`
  - Linux: `AI-IDE_完整依赖安装说明_Linux.md`
- AI-IDE 渲染层启动时会自动优先打开当前平台对应的说明文件。
- AI-IDE 设置页支持“自动检测系统 Python / 手动选择解释器 / 一键重启后端”。
- AI-IDE 后端 uvicorn 默认绑定 `127.0.0.1:8010`（仅本机访问，供 Electron 内置 AI-IDE 使用）。
- 主进程在 `app.whenReady` 阶段即拉起 AI-IDE 后端，再创建窗口，减少首屏进入 AI-IDE 时的 `127.0.0.1:8010` 连接拒绝。
- QMT Agent 已改为独立部署程序，不再由 Electron 主进程直接探测或控制本机 Agent 生命周期。
- 当前 Electron 仅负责用户维护能力：凭证初始化/重置、远端在线状态查看、独立安装包下载入口。

## 自动更新（Windows/macOS/Linux）

- 自动更新源支持按平台独立配置（`electron/main.ts`）：
  - `UPDATE_SERVER_URL_WIN`
  - `UPDATE_SERVER_URL_MAC`
  - `UPDATE_SERVER_URL_LINUX`
  - 通用回退：`UPDATE_SERVER_URL`
- 优先级：平台变量 > 通用变量 > `https://cos.quantmind.cloud/update`
- 适用场景：Windows 与 macOS 走不同 CDN 路径时，可避免相互覆盖更新元数据。

## 窗口与导航栏策略

- 主窗口固定分辨率：`1440x1000`（`min/max` 同值）。
- 禁止窗口拉伸、最大化与全屏（`resizable=false`、`maximizable=false`、`fullscreenable=false`）。
- 保留应用菜单（用于“工具-重新加载”等动作与加速键），但隐藏窗口菜单栏显示（`setMenuBarVisibility(false)` + `setAutoHideMenuBar(true)`）。
- 重载快捷键兜底：
  - `CmdOrCtrl+R` / `F5`：普通重载
  - `CmdOrCtrl+Shift+R`：忽略缓存重载
- 保留窗口最小化与关闭能力：
  - `window:minimize`：可用
  - `window:close`：可用
  - `window:maximize`：显式禁用（返回 `false`）
- 全平台圆角窗口：主进程统一使用 `transparent=false` 与 `roundedCorners=true`，渲染层根容器固定 `16px` 圆角裁剪，减少 Windows/macOS/Linux 的窗口圆角视觉差异。

## 生产包 index.html 路径兼容（2026-03）

- 主进程新增 `dist-react/index.html` 多候选路径解析，覆盖以下常见结构：
  - `app.getAppPath()/dist-react/index.html`
  - `../../dist-react/index.html`
  - `../dist-react/index.html`
  - `resources/app.asar/dist-react/index.html`
  - `resources/app/dist-react/index.html`
- 当未找到文件时，诊断页会展示“已检查路径列表”，便于快速定位打包产物结构问题。
