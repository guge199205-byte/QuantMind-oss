import json
import logging
import os
import re
from typing import Any, Dict

from openai import AsyncOpenAI

from .prompts import PARSER_SYSTEM_PROMPT
from .schema_retriever import SCHEMAS, get_schema_retriever
from .vector_parser import get_strategy_vector_parser

logger = logging.getLogger(__name__)


class IntentParser:
    def __init__(self):
        # 支持多种 LLM 配置（优先 DashScope，回退到 AI_IDE 通用配置）
        api_key = (
            os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("QWEN_API_KEY")
            or os.getenv("AI_IDE_LLM_API_KEY")
        )
        base_url = (
            os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("AI_IDE_LLM_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        model = (
            os.getenv("AI_STRATEGY_LLM_MODEL")
            or os.getenv("AI_IDE_LLM_MODEL")
            or "qwen3.6-flash"
        )

        if not api_key:
            logger.warning("No LLM API key configured for stock selection parser. "
                           "Set DASHSCOPE_API_KEY, QWEN_API_KEY, or AI_IDE_LLM_API_KEY.")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def parse(self, query: str) -> dict[str, Any]:
        try:
            # 已移除向量模型解析，直接使用 LLM 解析意图
            semantic_context = "大模型直接语义解析模式。"

            # Stage 1.5: Schema RAG（字段/表检索）
            retriever = await get_schema_retriever()
            schema_info = await retriever.retrieve(query, top_k=12)
            target_table = schema_info["target_table"]
            candidate_fields = schema_info["candidate_fields"]
            allowed_fields = set(schema_info["allowed_fields"])

            # 直接关键词匹配：用户查询中明确出现的字段名，强制追加到候选列表
            all_columns = SCHEMAS.get(target_table, [])
            query_lower = query.lower()
            candidate_names = {f["name"] for f in candidate_fields}
            extra_fields: list[dict] = []
            for col in all_columns:
                col_lower = col.name.lower()
                # 字段名长度 >= 3 且在用户查询中作为独立词出现（单词边界匹配）
                if len(col_lower) >= 3 and re.search(r"\b" + re.escape(col_lower) + r"\b", query_lower):
                    if col.name not in candidate_names:
                        extra_fields.append({"name": col.name, "description": col.description, "score": 1.0})
                        candidate_names.add(col.name)
            if extra_fields:
                candidate_fields = extra_fields + candidate_fields

            # Stage 2: Qwen 生成结构化过滤条件 (使用轻量化 flash 模型加速)
            formatted_system_prompt = PARSER_SYSTEM_PROMPT.format(
                semantic_context=semantic_context,
                target_table=target_table,
                candidate_fields="\n".join(f"- {f['name']}: {f['description']}" for f in candidate_fields)
                or "（无候选字段）",
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": formatted_system_prompt},
                    {"role": "user", "content": query},
                ],
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": True},
                timeout=30.0,  # 增加超时控制，防止网关 502
            )

            content = response.choices[0].message.content
            logger.info(f"Raw Qwen-flash intent response: {content}")

            if not content or not content.strip():
                logger.error("Empty content from LLM")
                return {
                    "filters": [],
                    "complex_logic": "Empty response",
                    "date_context": "2026-02-01",
                }

            result = json.loads(content)
            # 注入语义分类信息供后续使用
            result["semantic_category"] = "general"
            result["query"] = query
            result["target_table"] = result.get("target_table") or target_table

            # 过滤非法字段（大小写不敏感匹配）
            filters = result.get("filters") or []
            allowed_lower = {f.lower(): f for f in allowed_fields}
            sanitized_filters = []
            for f in filters:
                field = f.get("field")
                if field and field.lower() in allowed_lower:
                    f["field"] = allowed_lower[field.lower()]  # 规范化为正确大小写
                    sanitized_filters.append(f)
            result["filters"] = sanitized_filters
            result["fields_used"] = [f.get("field") for f in sanitized_filters if f.get("field")]
            result["candidate_fields"] = candidate_fields
            result["allowed_fields"] = list(allowed_fields)
            return result

        except Exception as e:
            logger.error(f"Selection intent parsing failed: {e}")
            return {
                "filters": [],
                "complex_logic": str(e),
                "date_context": "2026-02-01",
            }


_parser = None


def get_intent_parser():
    global _parser
    if _parser is None:
        _parser = IntentParser()
    return _parser
