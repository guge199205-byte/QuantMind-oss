# services

用途：服务层与数据访问逻辑。

## 说明
- 归属路径：electron\electron\services
- 修改本目录代码后请同步更新本 README
- `ai_ide_service.ts` 在检测/拉起内置 Python 时会清理宿主环境中的 `PYTHONHOME/PYTHONPATH` 等变量，避免便携版临时目录运行时被外部 Python 环境污染导致误判缺依赖。
- `ai_ide_service.ts` 会读取 `resources/python/<platform-arch>/BUILD_INFO.json`，并将 `bundleProfile/detectedBy` 透传给渲染层用于精确诊断。
- `ai_ide_service.ts` 的 core 依赖检测已改为直接 `__import__` 模块，避免 `importlib.util` 异常导致的“全部依赖误判缺失”。
- `ai_ide_service.ts` 的解释器解析优先级为：用户手动配置 > 工作区/项目虚拟环境 > 系统 Python > 打包内置 Python（最后兜底）。
- Windows 下系统 Python 探测会优先尝试 `py -3`，并解析到实际 `sys.executable` 路径后再作为解释器候选。
- `ai_ide_service.ts` 的 `pythonExists` 现为真实可执行探测（`--version`），不再把 `python/python3` 字符串视为“已安装”。
- `ai_ide_service.ts` 在打包环境会扫描 `resources/python/*/venv` 多目标目录作为候选解释器（优先当前平台架构），并逐个执行 `--version` 校验可执行性，避免“文件存在但不可运行（架构不匹配）”导致后端静默启动失败。
- QMT Agent 现按独立程序交付，不再在 `electron/electron/services` 下维护本机控制服务；Electron 仅保留远端凭证与状态相关能力。
