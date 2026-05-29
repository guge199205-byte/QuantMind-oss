# AI-IDE Service

本目录包含 AI-IDE 后端运行所需依赖清单。

## 近期更新

- AI-IDE 临时镜像安全验证（2026-04-10）：
  - AI-IDE 运行器默认仍使用后端配置的正式镜像 `AI_IDE_RUNNER_IMAGE`，默认值为 `quantmind-ml-runtime:latest`。
  - 前端可通过运行镜像覆盖参数显式切换到临时 tag；后端会先执行 smoke 验证，再决定是否启动真实策略容器。
  - 新增 `POST /api/v1/ai-ide/execute/smoke-image`，用于在正式运行前单独验证镜像是否可启动、关键依赖是否可导入，以及 stdout/stderr 是否可回传。
  - Smoke 默认会校验 `AI_IDE_SMOKE_IMPORTS` 指定的必需依赖（默认 `numpy,pandas`），可选依赖由 `AI_IDE_SMOKE_OPTIONAL_IMPORTS` 配置；`AI_IDE_SMOKE_ALLOW_PULL=false` 可禁止 smoke 时自动拉取镜像。
  - Smoke 容器采用只读文件系统、禁网、`--rm`、内存/CPU 限制和 `no-new-privileges`，用于把风险限制在一次性验证阶段。

- 工作区安全加固（2026-04-02）：
  - `workspace` 路由统一增加路径边界校验，所有读写/重命名/删除操作必须落在 `CURRENT_ROOT` 内。
  - `create/file`、`create/folder`、`rename`、`get/save/delete content` 已阻断 `../` 越界访问。
  - CORS 改为复用 `backend.shared.cors.resolve_cors_origins`，生产/预发不再默认 `*`。
- 默认工作区配置已改为平台无关写法：`config.json` 中的 `root_path` 允许为空，运行时会优先读取环境变量 `AI_IDE_PROJECT_ROOT`，否则自动回退到当前项目根目录。
- `run-tmp` 执行稳定性修复（2026-03-11）：
  - 修复 `AI_IDE_DATA_DIR` 已配置时 `project_root` 未定义导致的 `500`（浏览器侧常表现为 CORS + Failed to fetch）。
  - `run-tmp` 新增异常捕获与明确错误信息，便于前端直接定位执行失败原因。
- `run` 执行语义收敛（2026-04-10）：
  - AI-IDE 运行器会先检测策略文件是否具备可直接执行入口（`main/run` 或 `if __name__ == "__main__"`）。
  - 若文件仅包含 `STRATEGY_CONFIG`、`get_strategy_config()` 或策略类定义，后端会直接返回 422，并提示需要通过 Qlib 回测入口执行，而不是继续跑到容器内“静默结束”。
  - 前端日志流在异常断开时也会写入错误面板，避免用户只看到“3 秒后停止”却没有明确原因。
  - 前端已在模块型策略场景下自动转入 `Qlib` 异步回测入口，避免把策略配置文件误当成普通 Python 脚本执行。

## 依赖分层

- `requirements-minimal.txt`：最小运行依赖（`fastapi/uvicorn/pydantic/pydantic-settings/httpx/python-dotenv`），用于轻量打包与本地文件/执行基础能力。
- `requirements-core.txt`：AI-IDE 基础能力依赖（聊天、接口、配置等）。
- `requirements-quant.txt`：量化扩展依赖（`pyqlib`、`numpy/pandas` 等）。
- `requirements.txt`：全量聚合入口（兼容历史脚本），等价于：
  - `-r requirements-core.txt`
  - `-r requirements-quant.txt`

## 打包建议

- 追求最小安装包时可使用 `minimal` 档位（仅保留 AI-IDE 后端基础运行能力）。
- 生产默认建议使用 `core` 档位以降低安装包体积。
- 仅在需要完整本地量化能力时使用 `full` 档位。
- macOS 完整依赖安装说明见 [`docs/AI_IDE_macOS_环境依赖安装指南.md`](../../../docs/AI_IDE_macOS_环境依赖安装指南.md)。

## macOS 安装建议

- Apple Silicon：
  - 推荐 `requirements-core.txt`
  - 若需要量化扩展，建议手工安装 `pandas/numpy/akshare/scikit-learn/matplotlib`
  - 不建议默认依赖 `pyqlib`
- Intel Mac：
  - 可直接安装 `requirements-core.txt`
  - 需要完整量化能力时，再安装 `requirements-quant.txt`

示例命令：

```bash
cd <quantmind-root>
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r backend/services/ai_ide/requirements-core.txt
```

Intel Mac 量化扩展：

```bash
pip install -r backend/services/ai_ide/requirements-quant.txt
```

Apple Silicon 量化扩展：

```bash
pip install "pandas<2.0.0" "numpy<2.0.0" akshare "scikit-learn<1.6.0" matplotlib
```

## API Key 加载优先级

AI-IDE 聊天接口在运行时会动态刷新 API Key，优先级如下：

1. `AI_IDE_DATA_DIR/config.json` 中的 `qwen_api_key`
2. 环境变量 `AI_IDE_API_KEY`
3. 环境变量 `OPENAI_API_KEY`

这样在桌面端通过“设置”保存 Key 后，无需重启应用即可生效，并且重启后仍可恢复。

## LLM 默认配置

- 默认 `base_url`：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 默认 `model`：`qwen-plus`
- 可通过环境变量覆盖：
  - `AI_IDE_BASE_URL`
  - `AI_IDE_MODEL`

说明：当前桌面端设置页以 Qwen Key 为主，因此后端默认切换为 Qwen 兼容模式；若使用其他供应商，请显式设置上述环境变量。

## 运行镜像与 Smoke 配置

- `AI_IDE_RUNNER_IMAGE`：AI-IDE 正式运行镜像。若未设置，默认使用 `quantmind-ml-runtime:latest`。
- `AI_IDE_SMOKE_IMPORTS`：镜像 smoke 时必须成功导入的模块列表，逗号分隔。
- `AI_IDE_SMOKE_OPTIONAL_IMPORTS`：镜像 smoke 时可选导入的模块列表，逗号分隔。
- `AI_IDE_SMOKE_ALLOW_PULL`：是否允许 smoke 阶段在本地无镜像时自动拉取远端镜像，默认开启。
- `AI_IDE_SMOKE_CACHE_TTL_SECONDS`：smoke 通过后的缓存时长，默认 1800 秒。

前端 AI-IDE 页面提供“运行镜像（高级）”输入框；留空表示继续使用正式镜像。填写临时 tag 后，运行前会先完成一次临时镜像 smoke 验证，失败则阻断真实执行。

## 错误提示

- 未配置 API Key 时，`/api/v1/ai/chat` 返回中文友好提示，便于前端直接展示引导信息。
