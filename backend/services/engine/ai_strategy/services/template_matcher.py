"""
模板匹配服务
实现智能模板匹配算法
"""

import re
import time
from collections import Counter
from typing import Any, Dict, List

from ..models import (
    BUILTIN_TEMPLATES,
    StrategyTemplate,
    TemplateMatch,
    TemplateMatchRequest,
)

# 导入共享枚举
try:
    from shared.enums import is_valid_market, is_valid_risk_level, is_valid_timeframe
except ImportError:
    # 如果共享模块不可用，使用本地定义
    _StrategyCategory = str
    _MarketType = str
    _Timeframe = str
    _RiskLevel = str

    def is_valid_risk_level(x):
        return x in ["low", "medium", "high"]

    def is_valid_market(x):
        return x in ["CN", "US", "HK", "GLOBAL"]

    def is_valid_timeframe(x):
        return x in ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]


class TemplateMatcher:
    """模板匹配器"""

    def __init__(self):
        self.weights = {
            "category": 0.20,  # 策略类别权重
            "description": 0.25,  # 描述相似度权重
            "parameters": 0.20,  # 参数匹配权重
            "risk_level": 0.15,  # 风险等级权重
            "market": 0.10,  # 市场适配权重
            "timeframe": 0.10,  # 时间框架权重
        }

    def match_templates(self, request: TemplateMatchRequest) -> list[TemplateMatch]:
        """
        匹配最适合的策略模板

        Args:
            request: 模板匹配请求

        Returns:
            匹配结果列表，按置信度排序
        """
        start_time = time.time()
        matches: list[TemplateMatch] = []

        # 提取用户关键词
        user_keywords = self._extract_keywords(request.user_description or "")

        # 分析用户参数
        user_params = request.user_params

        # 遍历所有模板进行匹配
        for template in BUILTIN_TEMPLATES:
            match_result = self._calculate_template_match(template, user_params, user_keywords)

            # 只返回满足最小置信度的匹配
            if match_result.confidence >= request.min_confidence:
                matches.append(match_result)

        # 按置信度排序并限制结果数量
        matches.sort(key=lambda x: x.confidence, reverse=True)
        matches = matches[: request.max_results]

        int((time.time() - start_time) * 1000)

        return matches

    def _calculate_template_match(
        self,
        template: StrategyTemplate,
        user_params: dict[str, Any],
        user_keywords: list[str],
    ) -> TemplateMatch:
        """计算单个模板的匹配度"""

        # 1. 类别匹配度
        category_score = self._calculate_category_score(user_params, template)

        # 2. 描述相似度
        description_score = self._calculate_description_similarity(
            user_params.get("description", ""),
            template.description,
            user_keywords,
            template.tags,
        )

        # 3. 参数匹配度
        parameter_score = self._calculate_parameter_match(user_params, template)

        # 4. 参数适配性
        fitness_score = self._calculate_parameter_fitness(user_params, template)

        # 5. 风险等级匹配度
        risk_level_score = self._calculate_risk_level_score(user_params, template)

        # 6. 市场适配度
        market_score = self._calculate_market_score(user_params, template)

        # 7. 时间框架适配度
        timeframe_score = self._calculate_timeframe_score(user_params, template)

        # 8. 标签匹配度
        tag_score = self._calculate_tag_match(user_keywords, template.tags)

        # 计算综合得分
        score = (
            category_score * self.weights["category"]
            + description_score * self.weights["description"]
            + parameter_score * self.weights["parameters"] * 0.6
            + fitness_score * self.weights["parameters"] * 0.4
            + risk_level_score * self.weights["risk_level"]
            + market_score * self.weights["market"]
            + timeframe_score * self.weights["timeframe"]
        )

        # 计算置信度（综合多个因素）
        confidence = min(1.0, score * 1.2 + tag_score * 0.2)

        # 生成匹配原因
        reasons = self._generate_match_reasons(
            template,
            category_score,
            description_score,
            parameter_score,
            risk_level_score,
            market_score,
            timeframe_score,
            tag_score,
        )

        # 生成适配建议
        adaptations = self._generate_adaptations(template, user_params)

        return TemplateMatch(
            template=template,
            _confidence=confidence,
            reason="; ".join(reasons),
            adaptations=adaptations,
            score=score,
            _match_factors={
                "category": category_score,
                "description": description_score,
                "parameters": parameter_score,
                "risk_level": risk_level_score,
            },
        )

    def _calculate_category_score(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算类别得分"""
        user_style = user_params.get("style", "")

        # 策略风格到类别的映射
        style_to_category = {
            "conservative": "mean_reversion",
            "balanced": "trend",
            "aggressive": "momentum",
            "custom": template.category,  # 如果是自定义，倾向于模板类别
        }

        expected_category = style_to_category.get(user_style, template.category)
        return 1.0 if expected_category == template.category else 0.3

    def _calculate_description_similarity(
        self,
        user_desc: str,
        template_desc: str,
        user_keywords: list[str],
        template_tags: list[str],
    ) -> float:
        """计算描述相似度"""
        if not user_desc:
            return 0.5

        # Jaccard相似度计算
        user_words = set(user_desc.lower().split())
        template_words = set(template_desc.lower().split())

        if not user_words or not template_words:
            return 0.5

        intersection = user_words.intersection(template_words)
        union = user_words.union(template_words)
        jaccard_similarity = len(intersection) / len(union)

        # 关键词匹配加分
        keyword_match = self._calculate_keyword_match(user_keywords, template_tags)

        # 综合得分
        return jaccard_similarity * 0.7 + keyword_match * 0.3

    def _calculate_keyword_match(self, user_keywords: list[str], template_tags: list[str]) -> float:
        """计算关键词匹配度"""
        if not user_keywords or not template_tags:
            return 0.0

        user_tag_set = set([kw.lower() for kw in user_keywords])
        template_tag_set = set([tag.lower() for tag in template_tags])

        intersection = user_tag_set.intersection(template_tag_set)
        union = user_tag_set.union(template_tag_set)

        return len(intersection) / len(union) if union else 0.0

    def _calculate_parameter_match(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算参数匹配度"""
        if not template.default_parameters:
            return 0.5

        matches = 0
        total = 0

        # 可比较的字段
        comparable_fields = [
            "market",
            "timeframe",
            "risk_level",
            "style",
            "strategy_length",
            "backtest_period",
        ]

        for field in comparable_fields:
            user_value = user_params.get(field)
            template_value = template.default_parameters.get(field)

            if user_value and template_value:
                total += 1
                if str(user_value).lower() == str(template_value).lower():
                    matches += 1
                else:
                    # 部分匹配评分
                    if field == "risk_level":
                        # 风险等级相邻级别给予部分分数
                        risk_levels = ["low", "medium", "high"]
                        try:
                            user_index = risk_levels.index(user_value.lower())
                            template_index = risk_levels.index(template_value.lower())
                            if abs(user_index - template_index) == 1:
                                matches += 0.5
                        except ValueError:
                            pass

        # 数值型参数的相似度计算
        numeric_fields = [
            "initial_capital",
            "max_drawdown",
            "commission_rate",
            "slippage",
        ]

        for field in numeric_fields:
            user_value = user_params.get(field)
            template_value = template.default_parameters.get(field)

            if user_value is not None and template_value is not None:
                total += 1
                try:
                    user_num = float(user_value)
                    template_num = float(template_value)
                    similarity = 1 - abs(user_num - template_num) / max(user_num, template_num)
                    matches += max(0, similarity)
                except (ValueError, ZeroDivisionError):
                    pass

        return matches / total if total > 0 else 0.5

    def _calculate_parameter_fitness(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算数值参数的适配性"""
        fitness = 1.0

        # 资金适配性
        user_capital = user_params.get("initial_capital")
        if user_capital and user_capital < template.min_capital:
            if user_capital < template.min_capital * 0.5:
                fitness *= 0.3  # 资金不足严重降低适配性
            else:
                fitness *= 0.8  # 资金刚好满足轻微降低适配性

        # 回撤适配性
        user_max_dd = user_params.get("max_drawdown")
        if user_max_dd and template.metadata.performance:
            template_max_dd_str = template.metadata.performance.get("maxDrawdown", "0%")
            try:
                template_max_dd = float(template_max_dd_str.rstrip("%"))
                if user_max_dd < template_max_dd * 0.5:
                    fitness *= 0.7  # 用户风险承受能力过低
            except (ValueError, AttributeError):
                pass

        # 市场适配性
        user_market = user_params.get("market")
        if user_market and user_market not in template.suitable_markets:
            fitness *= 0.5  # 市场不匹配降低适配性

        # 时间框架适配性
        user_timeframe = user_params.get("timeframe")
        if user_timeframe and user_timeframe not in template.suitable_timeframes:
            fitness *= 0.6  # 时间框架不匹配降低适配性

        # 风险等级适配性
        user_risk = user_params.get("risk_level")
        if user_risk and user_risk not in template.suitable_risk_levels:
            fitness *= 0.4  # 风险等级不匹配严重降低适配性

        return fitness

    def _calculate_risk_level_score(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算风险等级得分"""
        user_risk = user_params.get("risk_level")
        if not user_risk:
            return 0.5

        if user_risk in template.suitable_risk_levels:
            return 1.0

        # 邻近风险等级给予部分分数
        risk_levels = ["low", "medium", "high"]
        try:
            user_index = risk_levels.index(user_risk)
            for template_risk in template.suitable_risk_levels:
                template_index = risk_levels.index(template_risk)
                if abs(user_index - template_index) == 1:
                    return 0.6
        except ValueError:
            pass

        return 0.2

    def _calculate_market_score(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算市场适配得分"""
        user_market = user_params.get("market")
        if not user_market:
            return 0.5

        return 1.0 if user_market in template.suitable_markets else 0.3

    def _calculate_timeframe_score(self, user_params: dict[str, Any], template: StrategyTemplate) -> float:
        """计算时间框架适配得分"""
        user_timeframe = user_params.get("timeframe")
        if not user_timeframe:
            return 0.5

        return 1.0 if user_timeframe in template.suitable_timeframes else 0.4

    def _calculate_tag_match(self, user_keywords: list[str], template_tags: list[str]) -> float:
        """计算标签匹配度"""
        if not user_keywords or not template_tags:
            return 0.0

        user_tag_set = set([kw.lower() for kw in user_keywords])
        template_tag_set = set([tag.lower() for tag in template_tags])

        intersection = user_tag_set.intersection(template_tag_set)
        union = user_tag_set.union(template_tag_set)

        return len(intersection) / len(union) if union else 0.0

    def _generate_match_reasons(
        self,
        template: StrategyTemplate,
        category_score: float,
        description_score: float,
        parameter_score: float,
        risk_level_score: float,
        market_score: float,
        timeframe_score: float,
        tag_score: float,
    ) -> list[str]:
        """生成匹配原因"""
        reasons = []

        if category_score >= 0.8:
            reasons.append(f"策略类型匹配（{template.category}）")

        if description_score >= 0.7:
            reasons.append("描述高度相关")

        if parameter_score >= 0.7:
            reasons.append("参数配置匹配")

        if risk_level_score >= 0.8:
            reasons.append("风险等级适配")

        if market_score >= 0.8:
            reasons.append("市场环境适配")

        if timeframe_score >= 0.8:
            reasons.append("时间框架适配")

        if tag_score >= 0.5:
            reasons.append("标签匹配度高")

        if not reasons:
            reasons.append("基础匹配度达标")

        return reasons

    def _generate_adaptations(self, template: StrategyTemplate, user_params: dict[str, Any]) -> list[str]:
        """生成适配建议"""
        adaptations = []

        # 资金调整建议
        user_capital = user_params.get("initial_capital")
        if user_capital and user_capital < template.min_capital:
            adaptations.append(f"建议增加初始资金至{template.min_capital:,}元以上")

        # 参数调整建议
        user_risk = user_params.get("risk_level")
        if template.metadata.complexity == "high" and user_risk == "low":
            adaptations.append("建议降低策略复杂度或提高风险承受能力")
        elif template.metadata.complexity == "low" and user_risk == "high":
            adaptations.append("建议选择更复杂的策略以满足高风险偏好")

        # 市场调整建议
        user_market = user_params.get("market")
        if user_market and user_market not in template.suitable_markets:
            adaptations.append(f"建议切换到适合的市场：{', '.join(template.suitable_markets)}")

        # 时间框架调整建议
        user_timeframe = user_params.get("timeframe")
        if user_timeframe and user_timeframe not in template.suitable_timeframes:
            adaptations.append(f"建议调整时间框架为：{', '.join(template.suitable_timeframes)}")

        return adaptations

    def _extract_keywords(self, text: str) -> list[str]:
        """提取文本关键词"""
        if not text:
            return []

        # 移除标点符号并转为小写
        clean_text = re.sub(r"[^\w\s]", " ", text.lower())

        # 分词并过滤停用词
        stop_words = {
            "的",
            "是",
            "在",
            "和",
            "有",
            "我",
            "你",
            "他",
            "它",
            "我们",
            "你们",
            "他们",
            "this",
            "that",
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
        }

        words = [word for word in clean_text.split() if len(word) > 1 and word not in stop_words]

        # 统计词频并返回前10个关键词
        word_count = Counter(words)
        return [word for word, _ in word_count.most_common(10)]


# 全局模板匹配器实例
template_matcher = TemplateMatcher()
