# ✅ 已迁移至 engine

> **状态**: 迁移完成（2026-02-20）  
> **新路径**: `backend.services.engine.ai_strategy`  
> **外部引用**: `engine/main.py` 和 `engine/services/pipeline_service.py` 已全部更新为新路径  
> **内部引用**: 相对导入无需修改，包结构完整保留  
> **残留旧路径**: 无（`backend.ai_strategy.*` 引用已全部清除）

## 说明

此目录原为独立的 AI 策略生成服务，已整合到 **quantmind-engine** 服务中。

- `engine/main.py` 直接从 `backend.services.engine.ai_strategy.api.v1.*` 加载路由
- 5步向导生成流程、LLM 适配（Qwen/DeepSeek）、选股服务均在此目录

## 后续清理（可选）

当确认功能稳定后，可将此目录内容平铺到 `engine/ai/` 以简化包层级：
```
engine/
  ai/
    api/v1/routes.py      ← 现在: engine/ai_strategy/api/v1/routes.py
    api/v1/wizard.py
    selection/
    llm/
    generators/
```
届时需更新 `engine/main.py` 中的 import 路径。
| `services/selection/schema_retriever.py` | `backend/services/engine/ai/selection/` | `engine/main.py` (warmup) |
| `models.py` (StrategyGenerationRequest) | `backend/services/engine/ai/models.py` | `engine/services/pipeline_service.py` |
| `provider_registry.py` (get_provider) | `backend/services/engine/ai/provider_registry.py` | `engine/services/pipeline_service.py` |

**迁移步骤**：
1. 在 `backend/services/engine/` 下新建 `ai/` 子目录，将以上文件逐一移入。
2. 更新文件内所有 `from backend.ai_strategy.*` 为 `from backend.services.engine.ai.*`。
3. 同步修改 `engine/main.py` 和 `engine/services/pipeline_service.py` 中的 import。
4. 确认测试通过后，删除 `backend/ai_strategy/` 目录。

## 注意事项

- 不要删除此目录，直到确认所有外部引用已清理
- 如需修改，请在替代服务中操作
