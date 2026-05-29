"""
统一策略标签系统 - 后端验证模块
Unified Strategy Tags System - Backend Validation

提供标签验证、过滤和推荐功能

Author: QuantMind Team
Date: 2025-12-02
"""

from typing import Dict, List

# 策略标签定义（与前端保持一致）
STRATEGY_TAGS = {
    "type": [
        "CTA",
        "多因子",
        "趋势跟踪",
        "均值回归",
        "套利",
        "期权策略",
        "高频交易",
        "算法交易",
    ],
    "market": ["A股", "港股", "美股", "期货", "期权", "外汇", "数字货币"],
    "style": ["日内", "短线", "中线", "长线", "波段"],
    "risk": ["低风险", "中风险", "高风险"],
    "indicator": ["均线", "MACD", "KDJ", "RSI", "布林带", "成交量"],
}


def get_all_tags() -> list[str]:
    """获取所有有效标签列表"""
    all_tags = []
    for category_tags in STRATEGY_TAGS.values():
        all_tags.extend(category_tags)
    return all_tags


def is_valid_tag(tag: str) -> bool:
    """验证标签是否有效"""
    return tag in get_all_tags()


def validate_tags(tags: list[str]) -> dict[str, any]:
    """
    验证标签列表

    Args:
        tags: 待验证的标签列表

    Returns:
        验证结果字典，包含：
        - valid: 是否全部有效
        - valid_tags: 有效的标签
        - invalid_tags: 无效的标签
        - message: 提示信息
    """
    if not tags:
        return {
            "valid": True,
            "valid_tags": [],
            "invalid_tags": [],
            "message": "标签列表为空",
        }

    valid_tags = []
    invalid_tags = []

    for tag in tags:
        if is_valid_tag(tag):
            valid_tags.append(tag)
        else:
            invalid_tags.append(tag)

    return {
        "valid": len(invalid_tags) == 0,
        "valid_tags": valid_tags,
        "invalid_tags": invalid_tags,
        "message": ("验证通过" if len(invalid_tags) == 0 else f"发现{len(invalid_tags)}个无效标签"),
    }


def filter_valid_tags(tags: list[str]) -> list[str]:
    """过滤并返回有效的标签"""
    return [tag for tag in tags if is_valid_tag(tag)]


def group_tags_by_category(tags: list[str]) -> dict[str, list[str]]:
    """按分类分组标签"""
    grouped = {category: [] for category in STRATEGY_TAGS.keys()}

    for tag in tags:
        for category, category_tags in STRATEGY_TAGS.items():
            if tag in category_tags:
                grouped[category].append(tag)
                break

    return grouped


def recommend_tags(selected_tags: list[str], limit: int = 5) -> list[str]:
    """
    根据已选标签推荐相关标签

    Args:
        selected_tags: 已选择的标签
        limit: 推荐数量限制

    Returns:
        推荐的标签列表
    """
    grouped = group_tags_by_category(selected_tags)
    recommended = []

    # 如果选了CTA策略，推荐期货市场
    if "CTA" in grouped["type"] and "期货" not in grouped["market"]:
        recommended.append("期货")

    # 如果选了多因子策略，推荐A股
    if "多因子" in grouped["type"] and "A股" not in grouped["market"]:
        recommended.append("A股")

    # 如果选了市场但没选指标，推荐常用指标
    if len(grouped["market"]) > 0 and len(grouped["indicator"]) == 0:
        recommended.extend(["均线", "MACD", "RSI"])

    return recommended[:limit]


def search_tags(query: str) -> list[str]:
    """搜索标签（模糊匹配）"""
    query_lower = query.lower()
    all_tags = get_all_tags()
    return [tag for tag in all_tags if query_lower in tag.lower()]


def get_tags_by_category(category: str) -> list[str]:
    """获取指定分类的标签"""
    return STRATEGY_TAGS.get(category, [])


def normalize_tags(tags: list[str]) -> list[str]:
    """
    标准化标签列表

    - 去重
    - 过滤无效标签
    - 排序
    """
    # 去重并过滤
    valid_tags = list(set(filter_valid_tags(tags)))

    # 按分类排序
    sorted_tags = []
    for category in STRATEGY_TAGS.keys():
        category_tags = [tag for tag in valid_tags if tag in STRATEGY_TAGS[category]]
        sorted_tags.extend(sorted(category_tags))

    return sorted_tags


# 导出常用函数
__all__ = [
    "STRATEGY_TAGS",
    "get_all_tags",
    "is_valid_tag",
    "validate_tags",
    "filter_valid_tags",
    "group_tags_by_category",
    "recommend_tags",
    "search_tags",
    "get_tags_by_category",
    "normalize_tags",
]


# 测试代码
if __name__ == "__main__":
    # 测试验证
    test_tags = ["CTA", "A股", "无效标签", "日内", "高频交易"]
    result = validate_tags(test_tags)
    print("验证结果:", result)

    # 测试分组
    grouped = group_tags_by_category(filter_valid_tags(test_tags))
    print("分组结果:", grouped)

    # 测试推荐
    recommended = recommend_tags(["CTA", "日内"])
    print("推荐标签:", recommended)

    # 测试搜索
    search_result = search_tags("CTA")
    print("搜索结果:", search_result)
