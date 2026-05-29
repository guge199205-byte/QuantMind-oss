"""Qlib AI 修复路由"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.services.engine.qlib_app import get_qlib_service
from backend.services.engine.qlib_app.api.identity import _identity_from_request
from backend.services.engine.qlib_app.schemas.backtest import QlibAIFixRequest, QlibAIFixResponse
from backend.shared.utils import normalize_user_id

router = APIRouter(tags=["qlib"])


@router.post("/ai-fix", response_model=QlibAIFixResponse)
async def ai_fix_strategy(
    request_ctx: Request,
    request: QlibAIFixRequest,
    service: Any = Depends(get_qlib_service),
) -> QlibAIFixResponse:
    """AI 智能修复策略代码"""
    try:
        if request is None and isinstance(request_ctx, QlibAIFixRequest):
            request = request_ctx
            request_ctx = None

        if request is None:
            raise HTTPException(status_code=422, detail="invalid request payload")

        if request_ctx is None:
            from backend.services.engine.qlib_app.services.backtest_persistence import BacktestPersistence
            from backend.services.engine.qlib_app.services.user_strategy_loader import UserStrategyLoader

            try:
                from backend.services.engine.ai_strategy.services.strategy_service import StrategyService
            except ImportError:
                from ai_strategy.services.strategy_service import StrategyService

            persistence = BacktestPersistence()
            run_data = await persistence.get_result(request.backtest_id)
            if not run_data:
                return QlibAIFixResponse(success=False, message="找不到对应的回测记录")

            if isinstance(run_data, dict):
                config = run_data.get("config", {})
            else:
                config = getattr(run_data, "config", {}) or {}

            original_code = config.get("strategy_content")
            if not original_code:
                return QlibAIFixResponse(success=False, message="该回测不包含自定义策略代码，无法修复")

            ai_service = StrategyService()
            repaired_code = await ai_service.generate_strategy_direct(
                f"错误信息: {request.error_message or ''}\n堆栈: {request.full_error or ''}\n\n原始代码:\n{original_code}"
            )
            if not repaired_code:
                return QlibAIFixResponse(success=False, message="AI 未能生成有效的修复方案")
            if repaired_code.startswith("```"):
                repaired_code = repaired_code.split("\n", 1)[-1]
                repaired_code = repaired_code.rsplit("```", 1)[0].strip()

            loader = UserStrategyLoader()
            strategy_id = config.get("strategy_id")
            try:
                save_result = loader.save_strategy(
                    user_id=str(config.get("user_id", "1")),
                    strategy_id=str(strategy_id) if strategy_id is not None else None,
                    strategy_name=config.get("name") or "AI修复策略",
                    code=repaired_code,
                    tenant_id=str(config.get("tenant_id", "default")),
                )
            except TypeError:
                save_result = loader.save_strategy(
                    code=repaired_code,
                    metadata={
                        "name": config.get("name") or "AI修复策略",
                        "user_id": str(config.get("user_id", "1")),
                        "tenant_id": str(config.get("tenant_id", "default")),
                    },
                    strategy_id=str(strategy_id) if strategy_id is not None else None,
                )
            if hasattr(save_result, "__await__"):
                save_result = await save_result

            return QlibAIFixResponse(
                success=True,
                repaired_code=repaired_code,
                strategy_id=str(save_result) if save_result else None,
                message="策略修复成功",
            )

        auth_user_id, auth_tenant_id = _identity_from_request(request_ctx)

        from backend.services.engine.qlib_app.services.backtest_persistence import BacktestPersistence
        from backend.services.engine.qlib_app.services.user_strategy_loader import UserStrategyLoader

        try:
            from backend.services.engine.ai_strategy.services.strategy_service import StrategyService
        except ImportError:
            from ai_strategy.services.strategy_service import StrategyService

        persistence = BacktestPersistence()
        run_data = await persistence.get_result(
            request.backtest_id,
            tenant_id=auth_tenant_id,
            user_id=auth_user_id,
        )

        if not run_data:
            from backend.shared.database_manager_v2 import get_session

            async with get_session(read_only=True) as session:
                from sqlalchemy import text

                row = await session.execute(
                    text(
                        "SELECT config_json, user_id, tenant_id FROM qlib_backtest_runs "
                        "WHERE backtest_id = :bid AND user_id = :uid AND tenant_id = :tid"
                    ),
                    {
                        "bid": request.backtest_id,
                        "uid": normalize_user_id(auth_user_id),
                        "tid": auth_tenant_id,
                    },
                )
                row = row.fetchone()
                if not row:
                    return QlibAIFixResponse(success=False, message="找不到对应的回测记录")
                config = row[0]
                user_id = row[1]
                tenant_id = row[2]
        else:
            if isinstance(run_data, dict):
                config = run_data.get("config", {})
                user_id = run_data.get("user_id", "default")
                tenant_id = run_data.get("tenant_id", "default")
            else:
                config = getattr(run_data, "config", {}) or {}
                user_id = getattr(run_data, "user_id", "default") or "default"
                tenant_id = getattr(run_data, "tenant_id", "default") or "default"

        if normalize_user_id(str(user_id)) != normalize_user_id(auth_user_id) or str(tenant_id) != str(auth_tenant_id):
            raise HTTPException(status_code=403, detail="未授权访问该回测记录")

        original_code = config.get("strategy_content")
        if not original_code:
            return QlibAIFixResponse(success=False, message="该回测不包含自定义策略代码，无法修复")

        from backend.services.engine.ai_strategy.services.strategy_service import get_strategy_service

        ai_service = get_strategy_service()
        diagnostic_prompt = f"""
你是 QuantMind 量化平台的代码精简专家。任务：**修复错误 + 大幅删减冗余代码**，输出极简可运行策略。

【平台规范（必须遵守）】
- 引擎入口：必须有 get_strategy_config() 函数 或 STRATEGY_CONFIG 字典
- 推荐基类：RedisRecordingStrategy（选股）/ RedisWeightStrategy（权重）
  导入：from backend.services.engine.qlib_app.utils.recording_strategy import RedisRecordingStrategy
- 信号：用 "signal": "<PRED>" 自动加载预测模型
- 禁止：import os/sys/subprocess/requests/urllib/socket
- TypeError 修复方向：__init__ 用 kwargs.pop() 消费自定义参数
- TypeError 修复方向：reset 使用 *args, **kwargs 并兼容 level_infra/common_infra/trade_exchange
- AssertionError 修复方向：generate_trade_decision 必须返回 TradeDecisionWO

【引擎兼容格式示例（仅展示必须的接口规范，非目标长度参考）】
```python
def get_strategy_config():
    return {{
        "class": "YourStrategyClass",
        "module_path": "__main__",
        "kwargs": {{"signal": "<PRED>", "topk": 50, "n_drop": 5}}
    }}
STRATEGY_CONFIG = get_strategy_config()
```

【错误信息】
{request.error_message or "未提供"}

【堆栈信息】
{request.full_error or "未提供"}

【原始代码（需要精简修复）】
```python
{original_code}
```

【输出要求（精简但不丢失业务逻辑）】
1. 【必须保留】所有业务方法的核心逻辑（stock pool 加载、市场状态判断、仓位计算、调仓判断等）。
2. 【必须删除】全部 docstring、行内注释、print/logging 语句、未使用的 import。
3. 【必须删除】if __name__ == "__main__" 块、create_strategy_instance 等辅助函数。
4. 【必须修复】__init__ 自定义参数改用 kwargs.pop() 消费，避免传给父类导致 TypeError。
5. 【必须修复】generate_trade_decision 返回 TradeDecisionWO，不能返回 dict。
6. 【必须修复】若定义 reset，必须使用 reset(self, *args, **kwargs) 并加入 level_infra/common_infra/trade_exchange 回退。
7. 【硬编码简化】__init__ 参数 > 5 个时，将非关键参数用合理默认值硬编码替代。
8. 目标行数：删除注释/demo 后的自然行数（通常为原始行数的 30%~50%），严禁为压缩行数而丢弃业务逻辑。
9. 直接输出纯 Python 代码，不要任何 Markdown 标记或解释文字。
"""
        repaired_code = await ai_service.generate_strategy_direct(diagnostic_prompt)

        if not repaired_code or "import" not in repaired_code:
            return QlibAIFixResponse(success=False, message="AI 未能生成有效的修复方案")

        if repaired_code.startswith("```"):
            repaired_code = repaired_code.split("\n", 1)[-1]
            repaired_code = repaired_code.rsplit("```", 1)[0].strip()

        loader = UserStrategyLoader()
        strategy_id = config.get("strategy_id")
        strategy_name = config.get("name")

        if not strategy_name:
            import re as _re

            cls_match = _re.search(r"^class\s+(\w+)", original_code, _re.MULTILINE)
            fn_match = _re.search(r"^def\s+(get_strategy_config)\s*\(", original_code, _re.MULTILINE)
            if cls_match:
                strategy_name = cls_match.group(1)
            elif fn_match:
                strategy_name = f"CustomStrategy_{datetime.now().strftime('%m%d_%H%M')}"
            else:
                strategy_name = f"AI修复策略_{datetime.now().strftime('%m%d_%H%M')}"
        original_name = strategy_name

        if user_id == "default":
            user_id = "1"

        if not strategy_id and strategy_name:
            try:
                from backend.shared.strategy_storage import get_strategy_storage_service

                svc = get_strategy_storage_service()
                user_strategies = svc.list(user_id=user_id, search=strategy_name)
                for s in user_strategies:
                    if s.get("name") == strategy_name:
                        strategy_id = str(s.get("id"))
                        break

                if not strategy_id:
                    all_strategies = svc.list(user_id="1", search=strategy_name)
                    for s in all_strategies:
                        if s.get("name") == strategy_name:
                            strategy_id = str(s.get("id"))
                            user_id = str(s.get("user_id", user_id))
                            break
            except Exception:
                pass

        if not strategy_id:
            try:
                original_code_for_search = config.get("strategy_content")
                if original_code_for_search and len(original_code_for_search) > 100:
                    from backend.shared.strategy_storage import _code_hash

                    search_hash = _code_hash(original_code_for_search)
                    try:
                        from backend.shared.database_pool import get_db
                    except ImportError:
                        try:
                            from backend.shared.database_manager_v2 import sync_session_maker as get_db
                        except ImportError:
                            get_db = None

                    from sqlalchemy import text

                    if get_db:
                        with get_db() as session:
                            res = (
                                session.execute(
                                    text(
                                        "SELECT id, name, user_id FROM strategies WHERE code_hash = :code_hash AND status != 'deleted' ORDER BY updated_at DESC LIMIT 1"
                                    ),
                                    {"code_hash": search_hash},
                                )
                                .mappings()
                                .first()
                            )
                            if res:
                                strategy_id = str(res["id"])
                                strategy_name = res["name"]
                                original_name = strategy_name
                                user_id = str(res["user_id"])
            except Exception:
                pass

        try:
            try:
                from backend.services.engine.qlib_app.services.user_strategy_loader import _validate_code

                _validate_code(repaired_code)
            except Exception as e:
                raise ValueError(f"AI 生成代码未通过安全校验: {e}")

            from backend.shared.strategy_storage import get_strategy_storage_service

            svc = get_strategy_storage_service()
            existing_config: dict[str, Any] = {}
            if strategy_id and strategy_id.isdigit():
                try:
                    existing = await svc.get(strategy_id=int(strategy_id), user_id=user_id)
                    if existing:
                        existing_config = existing.get("config") or {}
                        if isinstance(existing_config, str):
                            import json as _json

                            existing_config = _json.loads(existing_config) if existing_config else {}
                except Exception:
                    pass

            fix_history: list = existing_config.get("ai_fix_history", [])
            fix_history.append(
                {
                    "v": len(fix_history) + 1,
                    "fixed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error_summary": (request.error_message or "")[:200],
                    "backtest_id": request.backtest_id,
                    "original_code": original_code,
                }
            )
            merged_config = {**existing_config, "ai_fix_history": fix_history}

            save_metadata = {
                "name": original_name,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "tags": config.get("tags", []) + ["AI_FIXED"],
                "description": f"AI 修复 v{len(fix_history)}（{datetime.now().strftime('%m-%d %H:%M')}）",
                "config": merged_config,
            }

            result = await svc.save(
                user_id=user_id, name=original_name, code=repaired_code, metadata=save_metadata, strategy_id=strategy_id
            )
            new_id = result["id"]

            return QlibAIFixResponse(
                success=True,
                repaired_code=repaired_code,
                strategy_id=new_id,
                message=f"策略已修复（v{len(fix_history)}），历史版本已归档，请重新执行回测验证",
            )
        except Exception as save_err:
            return QlibAIFixResponse(
                success=False, repaired_code=repaired_code, message=f"AI 已生成修复方案，但保存失败: {str(save_err)}"
            )

    except Exception as e:
        return QlibAIFixResponse(success=False, message=f"修复失败: {str(e)}")
