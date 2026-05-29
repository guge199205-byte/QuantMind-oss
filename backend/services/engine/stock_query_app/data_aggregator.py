#!/usr/bin/env python3
"""
数据整合器

整合LLM解析结果和Tushare数据,执行复杂的筛选逻辑。

Author: QuantMind Team
Version: 1.0.0
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from .llm_parser import ParsedQuery, ScreenCondition
from .local_models import SessionLocal, StockBasicInfo, StockRealTimeData

logger = logging.getLogger(__name__)

# stream 服务地址（可通过环境变量覆盖）
STREAM_BASE_URL = os.getenv("STREAM_SERVICE_URL", "http://localhost:8003")


class DataAggregator:
    """数据整合器

    负责:
    1. 根据解析后的条件从本地数据库获取数据
    2. 应用筛选逻辑
    3. 排序和分页
    """

    def __init__(self, session_factory=None):
        """初始化数据整合器

        Args:
            session_factory: 数据库会话工厂
        """
        self.session_factory = session_factory or SessionLocal

    def aggregate(self, parsed_query: ParsedQuery) -> dict[str, Any]:
        """执行数据整合和筛选"""
        start_time = datetime.now()
        session = self.session_factory()

        try:
            logger.info(f"开始数据整合,条件数: {len(parsed_query.conditions)}")

            # 1. 构建基础查询
            query = session.query(StockBasicInfo).filter(StockBasicInfo.status == 1)

            # 2. 应用各种筛选条件
            query = self._apply_filters(query, parsed_query.conditions)

            # 3. 排序
            # 注意: 复杂排序可能需要 Join StockRealTimeData，这里先简化处理
            if parsed_query.sort_by:
                query = self._apply_sorting(query, parsed_query.sort_by, parsed_query.sort_order)

            # 4. 获取总数
            total = query.count()

            # 5. 分页
            stocks = query.offset(0).limit(parsed_query.limit).all()

            # 6. 转换为列表
            results = [stock.to_dict() for stock in stocks]

            # 如果需要实时数据(PE/PB等)，可以在这里补充查询最新实时数据
            # 简化起见，假设StockBasicInfo已经包含了部分快照数据，或者按需补充
            self._enrich_realtime_data(session, results)

            # 7. 构建条件描述
            condition_descs = self._build_condition_descriptions(parsed_query.conditions)

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "message": f"筛选成功,共找到 {total} 只股票",
                "data": results,
                "total": total,
                "conditions": condition_descs,
                "explanation": parsed_query.explanation,
                "execution_time": execution_time,
            }

        except Exception as e:
            logger.error(f"数据整合失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"筛选失败: {str(e)}",
                "data": [],
                "total": 0,
                "conditions": [],
            }
        finally:
            session.close()

    def _apply_filters(self, query, conditions: list[ScreenCondition]):
        """应用筛选条件"""
        for cond in conditions:
            # 市场筛选
            if cond.type == "market":
                if cond.categories:
                    # 转换市场代码格式: SH -> MarketType.SH (需要匹配DB存储格式)
                    # DB存储的是 'SH', 'SZ' 等字符串
                    query = query.filter(StockBasicInfo.exchange.in_(cond.categories))

            # 行业筛选
            elif cond.type == "industry":
                if cond.categories:
                    if cond.mode == "include":
                        query = query.filter(StockBasicInfo.industry.in_(cond.categories))
                    elif cond.mode == "exclude":
                        query = query.filter(StockBasicInfo.industry.notin_(cond.categories))

            # 市值筛选 (market_cap 单位: 亿元 -> DB可能是万元或元，假设DB是万元，需统一)
            # local_models.py 注释: market_cap comment="市值" (未说明单位，假设万元)
            # LLM parser 默认 market_cap 是亿元
            elif cond.type == "market_cap":
                # 假设 DB 中 market_cap 单位为万元，条件单位为亿元
                # 1亿 = 10000万
                idx_factor = 10000
                if cond.min_value:
                    query = query.filter(StockBasicInfo.market_cap >= cond.min_value * idx_factor)
                if cond.max_value:
                    query = query.filter(StockBasicInfo.market_cap <= cond.max_value * idx_factor)

            # 价格筛选
            elif cond.type == "price_range":
                if cond.min_value:
                    query = query.filter(StockBasicInfo.price >= cond.min_value)
                if cond.max_value:
                    query = query.filter(StockBasicInfo.price <= cond.max_value)

            # 涨跌幅
            elif cond.type == "change_pct":
                if cond.min_value:
                    query = query.filter(StockBasicInfo.change_pct >= cond.min_value)
                if cond.max_value:
                    query = query.filter(StockBasicInfo.change_pct <= cond.max_value)

            # 其他指标如 PE/PB，需要关联 StockRealTimeData 表，或者 StockBasicInfo 表有缓存
            # local_models.py StockBasicInfo 没有 PE/PB
            # 这里暂时不支持复杂关联筛选，提示用户 TODO
            elif cond.type in ["pe_ratio", "pb_ratio"]:
                logger.warning(f"暂不支持 DB 筛选 {cond.type} (字段不在 StockBasicInfo 表中)")

        return query

    def _apply_sorting(self, query, sort_by, sort_order):
        """应用排序"""

        # 字段映射
        field_map = {
            "market_cap": StockBasicInfo.market_cap,
            "price": StockBasicInfo.price,
            "change_pct": StockBasicInfo.change_pct,
        }

        sort_field = field_map.get(sort_by)
        if sort_field is not None:
            if sort_order == "desc":
                query = query.order_by(desc(sort_field))
            else:
                query = query.order_by(sort_field)

        return query

    def _enrich_realtime_data(self, session, results):
        """补充实时数据（优先从 stream 服务获取，降级为本地 DB）"""
        codes = [r["stock_code"] for r in results]
        if not codes:
            return

        # 1. 尝试从 stream 服务批量获取实时行情
        stream_quotes = self._fetch_quotes_from_stream(codes)

        for r in results:
            code = r["stock_code"]
            if code in stream_quotes:
                q = stream_quotes[code]
                r.setdefault("now_price", q.get("now"))
                r.setdefault("open_price", q.get("open"))
                r.setdefault("data_source", "stream")
            else:
                # 2. 降级：从本地 StockRealTimeData 取最新记录
                rt = (
                    session.query(StockRealTimeData)
                    .filter(StockRealTimeData.stock_code == code)
                    .order_by(StockRealTimeData.trade_date.desc())
                    .first()
                )
                if rt:
                    r.setdefault("now_price", rt.close)
                    r.setdefault("data_source", "local_db")

    def _fetch_quotes_from_stream(self, codes: list[str]) -> dict[str, Any]:
        """调用 stream 服务获取行情快照，返回 {code: quote_dict}"""
        try:
            import httpx

            quotes: dict[str, Any] = {}
            # stream 服务单次查询一个标的，批量串行（生产可改为 asyncio.gather）
            with httpx.Client(base_url=STREAM_BASE_URL, timeout=2.0) as client:
                for code in codes[:20]:  # 单次最多补充 20 支，避免超时
                    market = "SH" if code.startswith("6") else "SZ"
                    try:
                        resp = client.get(f"/api/v1/quotes/{code}.{market}")
                        if resp.status_code == 200:
                            quotes[code] = resp.json()
                    except Exception:
                        pass  # 单支失败不影响其他
            return quotes
        except ImportError:
            logger.debug("httpx 未安装，跳过 stream 行情补充")
            return {}
        except Exception as e:
            logger.debug("stream 行情服务不可用，降级到本地 DB: %s", e)
            return {}

    def _find_condition(self, conditions: list[ScreenCondition], cond_type: str) -> ScreenCondition | None:
        """查找指定类型的条件"""
        for cond in conditions:
            if cond.type == cond_type:
                return cond
        return None

    def _build_condition_descriptions(self, conditions: list[ScreenCondition]) -> list[str]:
        """构建条件描述"""
        descriptions = []

        for cond in conditions:
            desc = self._describe_condition(cond)
            if desc:
                descriptions.append(desc)

        return descriptions

    def _describe_condition(self, cond: ScreenCondition) -> str:
        """描述单个条件"""
        if cond.type == "market_cap":
            parts = []
            if cond.min_value:
                parts.append(f"市值>={cond.min_value}亿")
            if cond.max_value:
                parts.append(f"市值<={cond.max_value}亿")
            return "、".join(parts) if parts else "市值筛选"

        elif cond.type == "industry":
            if cond.mode == "include":
                return f"行业: {', '.join(cond.categories or [])}"
            else:
                return f"排除行业: {', '.join(cond.categories or [])}"

        elif cond.type == "pe_ratio":
            parts = []
            if cond.min_value:
                parts.append(f"PE>={cond.min_value}")
            if cond.max_value:
                parts.append(f"PE<={cond.max_value}")
            return "、".join(parts) if parts else "PE筛选"

        elif cond.type == "pb_ratio":
            parts = []
            if cond.min_value:
                parts.append(f"PB>={cond.min_value}")
            if cond.max_value:
                parts.append(f"PB<={cond.max_value}")
            return "、".join(parts) if parts else "PB筛选"

        elif cond.type == "market":
            if cond.categories:
                return f"市场: {', '.join(cond.categories)}"

        return cond.type

    def _empty_result(self, message: str) -> dict[str, Any]:
        """返回空结果"""
        return {
            "success": True,
            "message": message,
            "data": [],
            "total": 0,
            "conditions": [],
            "execution_time": 0.0,
        }
