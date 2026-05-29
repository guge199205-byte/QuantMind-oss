#!/usr/bin/env python3
"""
智能选股API路由

提供基于LLM的自然语言选股接口。

Author: QuantMind Team
Version: 1.0.0
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .smart_screener import get_smart_screener

# 创建路由器
router = APIRouter(prefix="/api/smart-screener", tags=["智能选股"])


# ============= 请求/响应模型 =============


class SmartScreenRequest(BaseModel):
    """智能选股请求"""

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "query": "帮我找市值小于300亿的科技股",
                "limit": 50,
                "explain": True,
            }
        },
    )

    query: str = Field(..., description="自然语言查询", min_length=1)
    limit: int = Field(50, description="返回数量限制", ge=1, le=1000)
    explain: bool = Field(True, description="是否返回解析过程")


class RefineRequest(BaseModel):
    """细化查询请求"""

    session_id: str = Field(..., description="会话ID")
    query: str = Field(..., description="追加的查询条件")
    previous_result: dict[str, Any] = Field(..., description="之前的查询结果")


class QueryUnderstanding(BaseModel):
    """查询理解"""

    original: str = Field(..., description="原始查询")
    parsed_conditions: list[dict] = Field(..., description="解析的条件")
    explanation: str = Field(..., description="解析说明")


class SmartScreenResponse(BaseModel):
    """智能选股响应"""

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "success": True,
                "message": "筛选成功,共找到 45 只股票",
                "query_understood": {
                    "original": "市值小于300亿的科技股",
                    "parsed_conditions": [
                        {"type": "market_cap", "max_value": 300},
                        {"type": "industry", "categories": ["计算机", "电子"]},
                    ],
                    "explanation": "筛选市值小于300亿的科技行业股票",
                },
                "data": [],
                "total": 45,
                "conditions": ["市值<=300亿", "行业: 计算机、电子"],
                "execution_time": 1.23,
                "timestamp": "2024-12-05T15:00:00",
            }
        },
    )

    success: bool
    message: str = ""
    query_understood: QueryUnderstanding | None = None
    data: list[dict[str, Any]] = []
    total: int
    conditions: list[str] = []
    execution_time: float
    timestamp: str


class SuggestionsResponse(BaseModel):
    """查询建议响应"""

    suggestions: list[str]
    popular_queries: list[str]
    examples: list[dict[str, str]]


# ============= API端点 =============


@router.post("/query", response_model=SmartScreenResponse, summary="智能选股查询")
async def smart_screen_query(request: SmartScreenRequest):
    """
    智能选股查询

    使用自然语言描述选股条件,系统会自动解析并执行筛选。

    ## 支持的查询示例:

    - "市值小于300亿的科技股"
    - "PE低于20,PB小于3的低估值股票"
    - "近3天成交量持续走高,流通股比例小于30%"
    - "排除金融和地产行业,ROE大于15%的股票"
    - "沪深300成分股中,今年涨幅超过20%的"

    ## 支持的筛选条件:

    1. **市值**: 市值、总市值
    2. **估值**: PE、PB、PS、市盈率、市净率
    3. **流通股**: 流通股比例、流通率
    4. **行业**: 科技股、金融股、医药股等
    5. **市场**: 沪市、深市、主板、创业板、科创板
    6. **财务**: ROE、净资产收益率、营收增长率
    7. **行情**: 价格区间、成交量、涨跌幅

    ## 返回数据:

    返回筛选结果,包括:
    - 股票列表(代码、名称、行业等)
    - 查询理解说明
    - 筛选条件列表
    - 执行时间
    """

    try:
        # 获取智能选股服务
        screener = get_smart_screener(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

        # 检查服务状态
        if not screener.is_ready():
            raise HTTPException(
                status_code=503,
                detail="智能选股服务不可用,请检查配置(OPENAI_API_KEY)",
            )

        # 执行查询
        result = screener.screen(user_query=request.query, limit=request.limit, explain=request.explain)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/refine", response_model=SmartScreenResponse, summary="细化查询")
async def refine_query(request: RefineRequest):
    """
    细化查询(对话式)

    在之前的查询基础上,追加新的筛选条件。

    ## 使用场景:

    ```
    第一次查询: "市值小于300亿的股票"
    细化查询: "再加上ROE大于15%的条件"

    结果: 筛选出市值<300亿 且 ROE>15% 的股票
    ```
    """
    try:
        screener = get_smart_screener(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

        if not screener.is_ready():
            raise HTTPException(status_code=503, detail="服务不可用")

        result = screener.refine(
            session_id=request.session_id,
            additional_query=request.query,
            previous_result=request.previous_result,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"细化查询失败: {str(e)}")


@router.get("/suggestions", response_model=SuggestionsResponse, summary="获取查询建议")
async def get_suggestions():
    """
    获取查询建议

    返回常用的查询示例和热门查询,帮助用户快速开始。
    """
    return {
        "suggestions": [
            "市值小于100亿的小盘股",
            "PE低于20的低估值股票",
            "近期连续上涨的强势股",
            "ROE大于15%的优质股",
            "科技行业龙头股",
            "流通股比例低于30%的控盘股",
        ],
        "popular_queries": [
            "市值小于300亿的科技股",
            "PE低于20,PB小于3的价值股",
            "排除金融和地产,ROE大于15%",
            "近3天成交量持续走高",
            "流通股比例小于30%的小盘股",
        ],
        "examples": [
            {"query": "市值小于300亿的科技股", "description": "筛选小盘科技股"},
            {"query": "PE低于20且PB小于3的股票", "description": "寻找低估值股票"},
            {"query": "ROE大于15%,排除金融和地产", "description": "筛选高ROE非金融股"},
            {"query": "近一周涨幅超过10%,成交量持续放大", "description": "寻找强势股"},
        ],
    }


@router.get("/status", summary="检查服务状态")
async def check_status():
    """
    检查智能选股服务状态

    返回LLM的可用性状态。
    """
    try:
        screener = get_smart_screener(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

        llm_available = screener.llm_parser and screener.llm_parser.is_available()

        return {
            "status": "ready" if screener.is_ready() else "not_ready",
            "llm": {
                "available": llm_available,
                "model": screener.llm_parser.model if llm_available else None,
            },
            "message": "服务正常" if screener.is_ready() else "服务未就绪,请检查配置",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/", summary="API信息")
async def api_info():
    """
    获取API信息
    """
    return {
        "name": "智能选股API",
        "version": "1.0.0",
        "description": "基于LLM的自然语言选股服务",
        "features": ["自然语言查询", "智能条件解析", "多数据源整合", "对话式细化"],
        "endpoints": {
            "query": "POST /api/smart-screener/query - 智能选股查询",
            "refine": "POST /api/smart-screener/refine - 细化查询",
            "suggestions": "GET /api/smart-screener/suggestions - 获取建议",
            "status": "GET /api/smart-screener/status - 服务状态",
        },
    }
