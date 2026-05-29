# scripts

用途：构建与开发脚本。

## 说明
- 归属路径：electron\scripts
- 修改本目录代码后请同步更新本 README

## 脚本列表

- `copy-dist-electron.js`: 复制 `dist-react` 到 `dist-electron/dist-react`
- `copy-ai-ide-backend.js`: 复制 `backend/ai_ide_service` 到 `dist-electron/backend/ai_ide_service`
- `prepare-ai-ide-python.js`: 准备 AI-IDE 内置 Python 运行时（发布流程仅 `build:package`，固定 core 档位）；自动探测到 `.../bin` 路径时会归一化到可执行 runtime 根目录。
- `lint-changed.js`: 仅对 Git 变更的 `electron/src/**/*.ts(x)` 执行 ESLint（用于增量门禁）
- `lint-phase.js`: 分阶段执行 ESLint（phase1/2/3），用于存量 lint 清债
