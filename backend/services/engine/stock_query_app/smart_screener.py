#!/usr/bin/env python3
"""
智能选股服务

整合LLM解析、Tushare数据和筛选逻辑的核心服务。

Author: QuantMind Team
Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Any, Dict

from .data_aggregator import DataAggregator
from .llm_parser import LLMQueryParser, get_llm_parser
from .tushare_adapter import TushareAdapter, get_tushare_adapter

logger = logging.getLogger(__name__)


class SmartStockScreener:
    """智能选股服务

    提供基于自然语言的智能选股功能。

    工作流程:
    1. 用户输入自然语言查询
    2. LLM解析为结构化条件
    3. Tushare获取数据
    4. 数据整合和筛选
    5. 返回结果
    """

    def __init__(self, llm_parser: LLMQueryParser = None, tushare_adapter: TushareAdapter = None):
        """初始化智能选股服务

        Args:
            llm_parser: LLM解析器实例
            tushare_adapter: Tushare适配器实例（可选，不可用时由 stream 服务补充实时行情）
        """
        self.llm_parser = llm_parser
        self.tushare_adapter = tushare_adapter
        # DataAggregator 无需 tushare_adapter；实时行情通过 stream 服务补充
        self.data_aggregator = DataAggregator()

    def is_ready(self) -> bool:
        """检查服务是否就绪（仅要求 LLM 解析器可用，行情数据走 stream 降级链路）"""
        return self.llm_parser is not None and self.llm_parser.is_available()

    def screen(self, user_query: str, limit: int = 50, explain: bool = True) -> dict[str, Any]:
        """执行智能选股

        Args:
            user_query: 用户的自然语言查询
            limit: 返回结果数量限制
            explain: 是否返回解析说明

        Returns:
            筛选结果字典:
            {
                "success": bool,
                "message": str,
                "query_understood": {
                    "original": str,
                    "parsed_conditions": List[Dict],
                    "explanation": str
                },
                "data": List[Dict],
                "total": int,
                "conditions": List[str],
                "execution_time": float,
                "timestamp": str
            }
        """
        start_time = datetime.now()

        # 检查服务状态
        if not self.is_ready():
            return {
                "success": False,
                "message": "服务未就绪: 请检查 LLM 配置",
                "data": [],
                "total": 0,
            }

        try:
            logger.info(f"收到选股请求: {user_query}")

            # 1. LLM解析查询
            parsed_query = self.llm_parser.parse(user_query)

            if not parsed_query.conditions:
                return {
                    "success": False,
                    "message": "无法解析查询条件",
                    "query_understood": {
                        "original": user_query,
                        "explanation": parsed_query.explanation,
                    },
                    "data": [],
                    "total": 0,
                }

            # 覆盖limit参数
            if limit:
                parsed_query.limit = limit

            logger.info(f"LLM解析完成: {len(parsed_query.conditions)} 个条件")

            # 2. 数据整合和筛选
            result = self.data_aggregator.aggregate(parsed_query)

            # 3. 构建完整响应
            execution_time = (datetime.now() - start_time).total_seconds()

            response = {
                "success": result["success"],
                "message": result["message"],
                "data": result["data"],
                "total": result["total"],
                "conditions": result["conditions"],
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

            # 添加解析说明
            if explain:
                response["query_understood"] = {
                    "original": user_query,
                    "parsed_conditions": [c.to_dict() for c in parsed_query.conditions],
                    "explanation": result.get("explanation", parsed_query.explanation),
                }

            logger.info(f"筛选完成: 找到{result['total']}只股票, 耗时{execution_time:.2f}秒")

            return response

        except Exception as e:
            logger.error(f"智能选股失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"选股失败: {str(e)}",
                "data": [],
                "total": 0,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat(),
            }

    def refine(self, session_id: str, additional_query: str, previous_result: dict[str, Any]) -> dict[str, Any]:
        """细化查询(对话式)

        Args:
            session_id: 会话ID
            additional_query: 额外的查询条件
            previous_result: 之前的查询结果

        Returns:
            新的筛选结果
        """
        # 组合查询
        if "query_understood" in previous_result:
            original_query = previous_result["query_understood"]["original"]
            combined_query = f"{original_query}，{additional_query}"
        else:
            combined_query = additional_query

        # 执行新查询
        return self.screen(combined_query)


# 单例实例
_smart_screener = None


def get_smart_screener(openai_api_key: str = None, tushare_token: str = None) -> SmartStockScreener:
    """获取智能选股服务单例

    Args:
        openai_api_key: OpenAI API Key
        tushare_token: Tushare Token

    Returns:
        SmartStockScreener实例
    """
    global _smart_screener
    if _smart_screener is None:
        llm_parser = get_llm_parser(api_key=openai_api_key)
        tushare_adapter = get_tushare_adapter(token=tushare_token)
        _smart_screener = SmartStockScreener(llm_parser=llm_parser, tushare_adapter=tushare_adapter)
    return _smart_screener
