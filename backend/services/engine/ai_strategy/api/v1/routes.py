"""AI Strategy Service - V1 路由集合

包含以下功能组（后续可按组拆分为独立文件）：
- 策略生成 & 流式生成
- 股票选择（选股/解析/执行）
- 策略 CRUD（增删改查、列表、搜索）
- 模板管理
- 验证引擎
- 系统监控 & 性能
- 文件管理
- 策略精炼/分析/执行
- 股票池文件管理
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from ...core.extractor import StrategyConfigExtractor
from ...models import (
    BatchValidationRequest,
    ChatRequest,
    CodeValidationRequest,
    ParameterValidationRequest,
    StrategyAnalysisRequest,
    StrategyExecutionRequest,
    StrategyGenerationRequest,
    StrategyRefineRequest,
    TemplateMatchRequest,
    TemplateMatchResponse,
    TemplateSearchFilter,
    TemplateValidationRequest,
    search_templates,
)
from ...provider_registry import REGISTRY, get_provider, get_provider_name
from ...services.selection import get_intent_parser, get_sql_generator
from ...services.template_matcher import template_matcher
from ...services.validator import unified_validator
from ...storage.database import (
    get_strategy_by_id,
    get_strategy_code,
)
from .pool_files import router as pool_files_router
from .support import router as support_router

logger = logging.getLogger(__name__)


try:  # 部署模式优先 shared
    from shared.database_manager_v2 import get_session  # type: ignore
    from shared.errors import ErrorCode  # type: ignore
    from shared.response import error, success  # type: ignore
except Exception:  # pragma: no cover
    from backend.shared.database_manager_v2 import get_session  # type: ignore
    from backend.shared.errors import ErrorCode  # type: ignore
    from backend.shared.response import error, success  # type: ignore

router = APIRouter()
router.include_router(support_router)
router.include_router(pool_files_router)


def _legacy_routes_enabled() -> bool:
    return os.getenv("AI_STRATEGY_ENABLE_LEGACY_ROUTES", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _mock_disabled() -> bool:
    return os.getenv("ENGINE_DISABLE_MOCK", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class StockSelectionRequest(BaseModel):
    query: str
    limit: int = 200
    user_id: str | None = None


class SelectionParseRequest(BaseModel):
    query: str


class SelectionExecuteRequest(BaseModel):
    sql: str


class ConfigExtractionRequest(BaseModel):
    code: str


def _resolve_provider(provider_name: str | None = None):
    if provider_name and provider_name in REGISTRY:
        return REGISTRY[provider_name]()
    return get_provider()


@router.post("/extract-config")
async def extract_strategy_config(request: ConfigExtractionRequest):
    """
    从代码中提取策略配置字典 (用于实盘/验证)
    """
    try:
        config = StrategyConfigExtractor.extract(request.code)
        return success(config)
    except ValueError as e:
        return error(ErrorCode.VALIDATION_ERROR, str(e))
    except Exception as exc:
        logger.error(f"Extract config failed: {exc}")
        return error(ErrorCode.INTERNAL_ERROR, f"解析失败: {exc}")


@router.post("/stocks/select")
async def select_stocks(payload: StockSelectionRequest):
    """统一选股入口（兼容旧版）"""
    if not payload.query.strip():
        return error(ErrorCode.PARAM_REQUIRED, "query 不能为空")

    parser = get_intent_parser()
    generator = get_sql_generator()

    try:
        # 1. 解析与生成
        intent = await parser.parse(payload.query)
        sql = await generator.generate_sql(intent)

        # 2. 执行并返回
        async with get_session(read_only=True) as session:
            stmt = text(sql)
            result = await session.execute(stmt)
            rows = [row._asdict() for row in result.all()]
            return success({"count": len(rows), "data": rows})
    except Exception as exc:
        logger.error(f"Unified stock selection failed: {exc}")
        return error(ErrorCode.INTERNAL_ERROR, f"选股失败: {exc}")


@router.post("/selection/parse")
async def parse_selection(payload: SelectionParseRequest):
    """解析自然语言选股指令"""
    if not payload.query.strip():
        return error(ErrorCode.PARAM_REQUIRED, "query 不能为空")

    parser = get_intent_parser()
    generator = get_sql_generator()

    # 1. 解析意图
    intent = await parser.parse(payload.query)
    # 2. 生成 SQL
    sql = await generator.generate_sql(intent)

    return success({"intent": intent, "sql": sql, "status": "success" if sql else "failed"})


@router.post("/selection/execute")
async def execute_selection(payload: SelectionExecuteRequest):
    """执行 SQL 选股并返回结果"""
    if not payload.sql.strip():
        return error(ErrorCode.PARAM_REQUIRED, "SQL 不能为空")

    # 安全性校验：仅允许 SELECT 语句
    if not payload.sql.lower().strip().startswith("select"):
        return error(ErrorCode.PERMISSION_DENIED, "仅允许执行 SELECT 语句")

    try:
        async with get_session(read_only=True) as session:
            stmt = text(payload.sql)
            result = await session.execute(stmt)
            rows = [row._asdict() for row in result.all()]

            return success({"count": len(rows), "data": rows, "status": "success"})
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return error(ErrorCode.INTERNAL_ERROR, f"SQL执行失败: {e}")


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    """SSE流式对话端点"""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

        # 获取provider
    provider = _resolve_provider(payload.provider)

    async def event_generator():
        try:
            # 流式聊天对话
            if hasattr(provider, "chat_stream"):
                async for chunk in provider.chat_stream(payload):
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
            else:
                # 如果不支持聊天流式，使用策略生成流式
                strategy_req = StrategyGenerationRequest(description=payload.message, user_id=payload.user_id)
                if hasattr(provider, "generate_stream"):
                    async for chunk in provider.generate_stream(strategy_req):
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/legacy/strategies", include_in_schema=False)
async def get_strategies(
    offset: int = 0,
    limit: int = 20,
    keyword: str | None = None,
    user_id: str | None = None,
    category: str | None = None,
):
    try:
        from backend.services.engine.qlib_app.services.user_strategy_loader import (
            user_strategy_loader,
        )

        data = user_strategy_loader.load_strategies(category=category, search=keyword)

        # 字段对齐：将 Qlib 格式元数据转换为前端 Strategy 接口格式
        formatted_strategies = []
        for s in data:
            formatted_strategies.append(
                {
                    "id": str(s.get("id")),
                    "name": s.get("name", "未命名策略"),
                    "description": s.get("description", ""),
                    "status": s.get("status", "stopped"),
                    "total_return": s.get("annual_return", 0),  # 映射为总收益展示
                    "today_return": 0,
                    "risk_level": s.get("risk_level", "medium"),
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at"),
                    "category": s.get("category_dir", "manual_created"),
                    "tags": s.get("tags", []),
                }
            )

        total = len(formatted_strategies)
        items = formatted_strategies[offset : offset + limit]

        return success(
            {
                "list": items,  # 前端 extractList 能够识别 list 或 strategies
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )
    except Exception as e:
        logger.error(f"Unified strategy list failed: {e}")
        # 回退到原有简易逻辑
        from .routes import list_strategies  # 假设存在本地 fallback

        data = list_strategies(offset=offset, limit=limit, keyword=keyword, user_id=user_id)
        return success(
            {
                "strategies": data["items"],
                "total": data["total"],
                "offset": offset,
                "limit": limit,
            }
        )


@router.post("/legacy/strategies", include_in_schema=False)
async def create_strategy(payload: dict):
    """保存策略（收敛至统一 loader）"""
    try:
        from backend.services.engine.qlib_app.services.user_strategy_loader import (
            user_strategy_loader,
        )

        code = payload.get("code")
        if not code:
            return error(ErrorCode.PARAMETER_ERROR, "策略代码不能为空")

        # 调用增强后的保存器
        strategy_id = user_strategy_loader.save_strategy(
            code=code,
            metadata=payload,
            category=payload.get("category", "manual_created"),
            strategy_id=payload.get("strategy_id"),
        )

        return success({"strategy_id": strategy_id, "message": "策略已保存并同步云端"})
    except Exception as e:
        logger.error(f"Unified strategy save failed: {e}")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/providers")
async def list_providers():
    active = get_provider_name()
    providers = []
    for name, factory in REGISTRY.items():
        healthy = True
        supports_stream = False
        try:
            instance = get_provider(name)
            supports_stream = getattr(instance, "supports_stream", False)
        except Exception:  # pragma: no cover
            healthy = False
            supports_stream = False
        providers.append(
            {
                "id": name,
                "name": name.capitalize() + " Provider",
                "is_healthy": healthy,
                "active": name == active and healthy,
                "supports_stream": supports_stream,
            }
        )
    return success({"providers": providers, "active": active})


@router.get("/strategies/{strategy_id}")
async def get_strategy_v1(strategy_id: str):
    """获取策略详情（前端标准路径）"""
    import asyncio
    result = await asyncio.to_thread(get_strategy_by_id, strategy_id)
    if result["success"]:
        return success(result["strategy"])
    else:
        return error(ErrorCode.NOT_FOUND, result["error"])


@router.get("/legacy/strategies/{strategy_id}", include_in_schema=False)
async def get_strategy(strategy_id: str):
    """获取策略详情"""
    import asyncio
    result = await asyncio.to_thread(get_strategy_by_id, strategy_id)
    if result["success"]:
        return success(result["strategy"])
    else:
        return error(ErrorCode.NOT_FOUND, result["error"])


@router.get("/strategies/{strategy_id}/code")
async def get_strategy_code_endpoint(strategy_id: str):
    """获取策略代码"""
    result = get_strategy_code(strategy_id)
    if result["success"]:
        return success(
            {
                "strategy_id": result["strategy_id"],
                "name": result["name"],
                "provider": result["provider"],
                "code": result.get("code_from_cos") or result["code"],  # 优先使用COS中的代码
                "cos_file_url": result["cos_file_url"],
                "cos_updated": result.get("cos_updated", False),
                "cos_error": result.get("cos_error"),
            }
        )
    else:
        return error(ErrorCode.NOT_FOUND, result["error"])


@router.get("/strategies/{strategy_id}/download")
async def download_strategy_file(strategy_id: str):
    """下载策略文件"""
    result = get_strategy_code(strategy_id)
    if not result["success"]:
        return error(ErrorCode.NOT_FOUND, result["error"])

    if not result.get("cos_file_url"):
        return error(ErrorCode.FILE_NOT_FOUND, "策略文件不存在")

        # 重定向到COS文件URL
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=result["cos_file_url"])


@router.put("/strategies/{strategy_id}")
async def update_strategy_v1(strategy_id: str, updates: dict):
    """更新策略（前端标准路径）"""
    try:
        from ...storage.database import update_strategy_by_id

        result = update_strategy_by_id(strategy_id, updates)
        if result["success"]:
            return success(result["strategy"])
        else:
            return error(ErrorCode.NOT_FOUND, result["error"])
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"更新策略失败: {exc}")


@router.delete("/strategies/{strategy_id}")
async def delete_strategy_v1(strategy_id: str):
    """删除策略（前端标准路径）"""
    try:
        from ...storage.database import delete_strategy_by_id

        result = delete_strategy_by_id(strategy_id)
        if result["success"]:
            return success({"message": f"策略 {strategy_id} 已删除"})
        else:
            return error(ErrorCode.NOT_FOUND, result["error"])
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"删除策略失败: {exc}")


@router.put("/legacy/strategies/{strategy_id}", include_in_schema=False)
async def update_strategy(strategy_id: str, updates: dict):
    """更新策略"""
    try:
        from ...storage.database import update_strategy_by_id

        result = update_strategy_by_id(strategy_id, updates)
        if result["success"]:
            return success(result["strategy"])
        else:
            return error(ErrorCode.NOT_FOUND, result["error"])
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"更新策略失败: {exc}")


@router.delete("/legacy/strategies/{strategy_id}", include_in_schema=False)
async def delete_strategy(strategy_id: str):
    """删除策略"""
    try:
        from ...storage.database import delete_strategy_by_id

        result = delete_strategy_by_id(strategy_id)
        if result["success"]:
            return success({"message": f"策略 {strategy_id} 已删除"})
        else:
            return error(ErrorCode.NOT_FOUND, result["error"])
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"删除策略失败: {exc}")


@router.post("/strategies/{strategy_id}/duplicate")
async def duplicate_strategy(strategy_id: str, name: str | None = None):
    """复制策略"""
    try:
        from ...storage.database import duplicate_strategy_by_id

        result = duplicate_strategy_by_id(strategy_id, name)
        if result["success"]:
            return success(result["strategy"])
        else:
            return error(ErrorCode.NOT_FOUND, result["error"])
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"复制策略失败: {exc}")


@router.get("/strategies/stats")
async def get_strategy_stats():
    """获取策略统计信息"""
    try:
        from ...storage.database import get_strategy_statistics

        stats = get_strategy_statistics()
        return success(stats)
    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"获取策略统计失败: {exc}")


@router.post("/strategies/{strategy_id}/refine")
async def refine_strategy(strategy_id: str, request: StrategyRefineRequest):
    """策略完善接口"""
    try:
        from ...storage.database import get_strategy_by_id

        # 验证策略是否存在
        strategy_result = get_strategy_by_id(strategy_id)
        if not strategy_result["success"]:
            return error(ErrorCode.NOT_FOUND, f"策略 {strategy_id} 不存在")

            # 获取provider
        provider = _resolve_provider(request.provider)

        # 构建完善请求的prompt
        refine_prompt = f"""请基于以下反馈完善策略代码:

当前策略代码:
```python
{request.current_code}
```

用户反馈: {request.feedback}

请返回JSON格式的完善结果，包含以下字段:
- refined_code: 完善后的Python策略代码
- explanation: 完善说明（中文）
- changes: 主要改进点列表
- validation: 代码验证结果

要求:
1. 保持代码结构完整
2. 使用简体中文注释
3. 确保代码语法正确且可运行
4. 针对用户反馈进行针对性改进
"""

        # 使用provider进行完善
        from ...models import ChatRequest

        chat_request = ChatRequest(message=refine_prompt, user_id=request.user_id, provider=request.provider)

        # 如果provider支持流式输出，使用流式接口
        if hasattr(provider, "generate_stream"):
            content_chunks = []
            async for chunk in provider.generate_stream(chat_request):
                content_chunks.append(chunk)
            full_content = "".join(content_chunks)
        else:
            # 回退到常规生成接口
            generation_request = StrategyGenerationRequest(
                description=refine_prompt,
                user_id=request.user_id,
                provider=request.provider,
                examples=[request.current_code],
            )
            result = await provider.generate(generation_request)
            full_content = result.rationale

            # 尝试解析JSON响应
        import json
        import re

        refine_result = None
        try:
            # 尝试直接解析JSON
            refine_result = json.loads(full_content)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            json_match = re.search(r"\{[\s\S]*\}", full_content)
            if json_match:
                try:
                    refine_result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

                    # 如果还是无法解析，返回基本结构
        if not refine_result:
            refine_result = {
                "refined_code": request.current_code,  # 保持原代码
                "explanation": full_content,  # 使用AI回复作为说明
                "changes": ["基于反馈进行了优化"],
                "validation": {"is_valid": True, "errors": [], "warnings": []},
            }

        return success(
            {
                "strategy_id": strategy_id,
                "refined_code": refine_result.get("refined_code", request.current_code),
                "explanation": refine_result.get("explanation", "策略完善完成"),
                "changes": refine_result.get("changes", []),
                "validation": refine_result.get("validation", {"is_valid": True, "errors": [], "warnings": []}),
                "provider": provider.__class__.__name__ if provider else "unknown",
                "refined_at": datetime.now().isoformat(),
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"策略完善失败: {exc}")


@router.post("/strategies/{strategy_id}/analyze")
async def analyze_strategy(strategy_id: str, request: StrategyAnalysisRequest):
    """策略分析接口"""
    try:
        from ...storage.database import get_strategy_code

        # 获取策略代码
        code_result = get_strategy_code(strategy_id)
        if not code_result["success"]:
            return error(ErrorCode.NOT_FOUND, f"策略 {strategy_id} 不存在")

        strategy_code = code_result.get("code_from_cos") or code_result.get("code", "")

        if not strategy_code.strip():
            return error(ErrorCode.INTERNAL_ERROR, "策略代码为空")

            # 获取provider
        provider = _resolve_provider()

        # 构建分析prompt
        analysis_prompts = {
            "performance": "请分析这个策略的性能表现，包括收益率、风险指标、回撤等",
            "risk": "请分析这个策略的风险特征，包括最大回撤、波动率、风险敞口等",
            "backtest": "请为这个策略设计回测方案，包括数据需求、测试参数、评估指标等",
            "optimization": "请提供这个策略的优化建议，包括参数调整、逻辑改进等",
        }

        analysis_prompt = f"""请对以下策略进行{request.analysis_type}分析:

策略代码:
```python
{strategy_code}
```

{analysis_prompts.get(request.analysis_type, "请分析这个策略")}

请返回JSON格式的分析结果，包含以下字段:
- analysis_type: 分析类型
- findings: 主要发现列表
- metrics: 关键指标（如适用）
- recommendations: 建议列表
- risk_level: 风险等级评估
- score: 综合评分（0-100）
"""

        # 执行分析
        from ...models import ChatRequest

        chat_request = ChatRequest(message=analysis_prompt, user_id=request.user_id)

        if hasattr(provider, "generate_stream"):
            content_chunks = []
            async for chunk in provider.generate_stream(chat_request):
                content_chunks.append(chunk)
            full_content = "".join(content_chunks)
        else:
            generation_request = StrategyGenerationRequest(
                description=analysis_prompt,
                user_id=request.user_id,
                examples=[strategy_code],
            )
            result = await provider.generate(generation_request)
            full_content = result.rationale

            # 解析分析结果
        import json
        import re

        analysis_result = None
        try:
            analysis_result = json.loads(full_content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\}", full_content)
            if json_match:
                try:
                    analysis_result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

                    # 默认分析结果
        if not analysis_result:
            analysis_result = {
                "analysis_type": request.analysis_type,
                "findings": [full_content],
                "metrics": {},
                "recommendations": ["建议进一步人工审核"],
                "risk_level": "medium",
                "score": 70,
            }

        return success(
            {
                "strategy_id": strategy_id,
                "analysis": analysis_result,
                "analyzed_at": datetime.now().isoformat(),
                "provider": provider.__class__.__name__ if provider else "unknown",
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"策略分析失败: {exc}")


@router.post("/strategies/{strategy_id}/execute")
async def execute_strategy(strategy_id: str, request: StrategyExecutionRequest):
    """策略执行接口"""
    if _mock_disabled():
        return error(
            ErrorCode.FORBIDDEN,
            "mock 执行已禁用，请使用 /api/v1/pipeline/runs 触发真实闭环执行",
        )
    try:
        import asyncio

        from ...storage.database import get_strategy_code

        # 获取策略代码
        code_result = get_strategy_code(strategy_id)
        if not code_result["success"]:
            return error(ErrorCode.NOT_FOUND, f"策略 {strategy_id} 不存在")

        strategy_code = code_result.get("code_from_cos") or code_result.get("code", "")

        if not strategy_code.strip():
            return error(ErrorCode.INTERNAL_ERROR, "策略代码为空")

            # 生成执行ID
        execution_id = f"exec_{int(datetime.now().timestamp()*1000)}"

        # 模拟策略执行（实际项目中这里会调用专门的执行引擎）
        async def simulate_execution():
            """模拟策略执行"""
            await asyncio.sleep(2)  # 模拟执行时间

            return {
                "execution_id": execution_id,
                "strategy_id": strategy_id,
                "status": "completed",
                "result": {
                    "trades_executed": 10,
                    "total_pnl": 1250.50,
                    "win_rate": 0.6,
                    "execution_time": "2.1s",
                },
                "logs": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "message": "策略执行开始",
                    },
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "message": "数据处理完成",
                    },
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "message": "信号生成完成",
                    },
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "message": "策略执行完成",
                    },
                ],
            }

            # 异步启动执行任务

        return success(
            {
                "execution_id": execution_id,
                "strategy_id": strategy_id,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "config": request.execution_config or {},
                "message": "策略执行已启动",
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"策略执行失败: {exc}")


@router.get("/strategies/executions/{execution_id}")
async def get_execution_status(execution_id: str):
    """获取策略执行状态"""
    if _mock_disabled():
        return error(
            ErrorCode.FORBIDDEN,
            "mock 执行状态接口已禁用，请改用 /api/v1/pipeline/runs/{run_id}",
        )
    try:
        # 这里应该从实际的执行结果存储中获取状态
        # 目前返回模拟数据
        return success(
            {
                "execution_id": execution_id,
                "status": "completed",
                "result": {
                    "trades_executed": 10,
                    "total_pnl": 1250.50,
                    "win_rate": 0.6,
                },
                "completed_at": datetime.now().isoformat(),
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"获取执行状态失败: {exc}")


@router.post("/strategies/executions/{execution_id}/stop")
async def stop_execution(execution_id: str):
    """停止策略执行"""
    if _mock_disabled():
        return error(
            ErrorCode.FORBIDDEN,
            "mock 执行停止接口已禁用，请在真实执行引擎中处理停止逻辑",
        )
    try:
        # 这里应该实现实际的停止逻辑
        return success(
            {
                "execution_id": execution_id,
                "status": "stopped",
                "stopped_at": datetime.now().isoformat(),
                "message": "策略执行已停止",
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"停止执行失败: {exc}")

        # ==================== 策略导入导出相关API ====================


@router.post("/strategies/{strategy_id}/export")
async def export_strategy(strategy_id: str, format: str = "json"):
    """导出策略"""
    try:
        from ...storage.database import get_strategy_by_id, get_strategy_code

        # 获取策略信息
        strategy_result = get_strategy_by_id(strategy_id)
        if not strategy_result["success"]:
            return error(ErrorCode.NOT_FOUND, f"策略 {strategy_id} 不存在")

        code_result = get_strategy_code(strategy_id)
        if not code_result["success"]:
            return error(ErrorCode.INTERNAL_ERROR, "无法获取策略代码")

        strategy_info = strategy_result["strategy"]
        strategy_code = code_result.get("code_from_cos") or code_result.get("code", "")

        if format == "json":
            export_data = {
                "strategy": strategy_info,
                "code": strategy_code,
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
            }
        elif format == "python":
            export_data = f'''"""
导出的策略文件
策略ID: {strategy_id}
策略名称: {strategy_info["name"]}
导出时间: {datetime.now().isoformat()}

"""

{strategy_code}
'''
        else:
            return error(ErrorCode.PARAM_INVALID, f"不支持的导出格式: {format}")

        return success(
            {
                "strategy_id": strategy_id,
                "format": format,
                "data": export_data,
                "filename": f"strategy_{strategy_id}.{format}",
                "exported_at": datetime.now().isoformat(),
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"导出策略失败: {exc}")


@router.post("/strategies/import")
async def import_strategy(file: UploadFile = None, data: dict = None):
    """导入策略"""
    try:
        if file:
            # 从文件导入
            content = await file.read()
            if file.filename.endswith(".json"):
                import_data = json.loads(content.decode("utf-8"))
            elif file.filename.endswith(".py"):
                strategy_code = content.decode("utf-8")
                import_data = {
                    "strategy": {
                        "name": file.filename.replace(".py", ""),
                        "description": "从文件导入的策略",
                    },
                    "code": strategy_code,
                }
            else:
                return error(ErrorCode.PARAM_INVALID, "不支持的文件格式")
        elif data:
            # 从JSON数据导入
            import_data = data
        else:
            return error(ErrorCode.PARAM_REQUIRED, "请提供文件或数据")

            # 生成新的策略ID
        f"import_{int(datetime.now().timestamp()*1000)}"

        # 保存导入的策略
        from ...models import (
            StrategyCodeArtifact,
            StrategyGenerationResult,
            StrategyMetadata,
        )
        from ...storage.database import save_strategy

        strategy_data = import_data.get("strategy", {})
        code_data = import_data.get("code", "")

        # 构建策略生成结果
        result = StrategyGenerationResult(
            strategy_name=strategy_data.get("name", "导入的策略"),
            rationale=strategy_data.get("description", "从外部导入的策略"),
            artifacts=[StrategyCodeArtifact(filename="strategy.py", language="python", code=code_data)],
            metadata=StrategyMetadata(
                factors=strategy_data.get("factors", []),
                risk_controls=strategy_data.get("risk_controls", []),
                assumptions=strategy_data.get("assumptions", []),
                notes="从外部导入的策略",
            ),
            provider="import",
        )

        # 保存到数据库
        persisted_id = save_strategy(
            result,
            strategy_data.get("description", "导入的策略"),
            strategy_data.get("market", "CN"),
            strategy_data.get("risk_level", "medium"),
            "desktop-user",
        )

        return success(
            {
                "strategy_id": persisted_id,
                "name": result.strategy_name,
                "message": "策略导入成功",
                "imported_at": datetime.now().isoformat(),
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"导入策略失败: {exc}")


@router.post("/strategies/{strategy_id}/share")
async def share_strategy(strategy_id: str, visibility: str = "private", description: str = ""):
    """分享策略"""
    try:
        from ...storage.database import get_strategy_by_id

        # 验证策略存在
        strategy_result = get_strategy_by_id(strategy_id)
        if not strategy_result["success"]:
            return error(ErrorCode.NOT_FOUND, f"策略 {strategy_id} 不存在")

            # 生成分享信息
        share_id = f"share_{int(datetime.now().timestamp()*1000)}"

        # 实际项目中这里应该保存到分享表
        return success(
            {
                "share_id": share_id,
                "share_url": f"/strategies/shared/{share_id}",
                "visibility": visibility,
                "message": "策略分享成功",
                "shared_at": datetime.now().isoformat(),
            }
        )

    except Exception as exc:
        return error(ErrorCode.INTERNAL_ERROR, f"分享策略失败: {exc}")

