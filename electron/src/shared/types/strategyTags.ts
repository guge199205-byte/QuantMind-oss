/**
 * 统一策略标签系统
 * Unified Strategy Tags System
 *
 * 提供跨模块一致的策略标签定义和工具函数
 *
 * @author QuantMind Team
 * @date 2025-12-02
 */

/**
 * 策略标签分类
 */
export const STRATEGY_TAG_CATEGORIES = {
  /** 策略类型 */
  TYPE: 'type',
  /** 市场类型 */
  MARKET: 'market',
  /** 交易风格 */
  STYLE: 'style',
  /** 风险等级 */
  RISK: 'risk',
  /** 技术指标 */
  INDICATOR: 'indicator',
} as const;

export type StrategyTagCategory = typeof STRATEGY_TAG_CATEGORIES[keyof typeof STRATEGY_TAG_CATEGORIES];

/**
 * 策略标签定义
 */
export const STRATEGY_TAGS: Record<StrategyTagCategory, TagConfig[]> = {
  // 策略类型
  type: [
    { value: 'CTA', label: 'CTA策略', color: '#1890ff' },
    { value: '多因子', label: '多因子策略', color: '#52c41a' },
    { value: '趋势跟踪', label: '趋势跟踪', color: '#722ed1' },
    { value: '均值回归', label: '均值回归', color: '#eb2f96' },
    { value: '套利', label: '套利策略', color: '#fa8c16' },
    { value: '期权策略', label: '期权策略', color: '#13c2c2' },
    { value: '高频交易', label: '高频交易', color: '#faad14' },
    { value: '算法交易', label: '算法交易', color: '#2f54eb' },
  ],

  // 市场类型
  market: [
    { value: 'A股', label: 'A股市场', color: '#f5222d' },
    { value: '港股', label: '港股市场', color: '#fa541c' },
    { value: '美股', label: '美股市场', color: '#1890ff' },
    { value: '期货', label: '期货市场', color: '#faad14' },
    { value: '期权', label: '期权市场', color: '#722ed1' },
    { value: '外汇', label: '外汇市场', color: '#13c2c2' },
    { value: '数字货币', label: '数字货币', color: '#52c41a' },
  ],

  // 交易风格
  style: [
    { value: '日内', label: '日内交易', color: '#f5222d' },
    { value: '短线', label: '短线交易', color: '#fa8c16' },
    { value: '中线', label: '中线交易', color: '#1890ff' },
    { value: '长线', label: '长线投资', color: '#52c41a' },
    { value: '波段', label: '波段操作', color: '#722ed1' },
  ],

  // 风险等级
  risk: [
    { value: '低风险', label: '低风险', color: '#52c41a' },
    { value: '中风险', label: '中风险', color: '#faad14' },
    { value: '高风险', label: '高风险', color: '#f5222d' },
  ],

  // 技术指标
  indicator: [
    { value: '均线', label: '移动平均线', color: '#1890ff' },
    { value: 'MACD', label: 'MACD', color: '#722ed1' },
    { value: 'KDJ', label: 'KDJ', color: '#eb2f96' },
    { value: 'RSI', label: 'RSI', color: '#fa8c16' },
    { value: '布林带', label: '布林带', color: '#13c2c2' },
    { value: '成交量', label: '成交量指标', color: '#52c41a' },
  ],
};

/**
 * 标签配置类型
 */
export interface TagConfig {
  value: string;
  label: string;
  color: string;
}

/**
 * 获取所有标签（扁平化）
 */
export function getAllTags(): TagConfig[] {
  return Object.values(STRATEGY_TAGS).flat();
}

/**
 * 根据分类获取标签
 */
export function getTagsByCategory(category: StrategyTagCategory): TagConfig[] {
  return STRATEGY_TAGS[category] || [];
}

/**
 * 根据值查找标签配置
 */
export function findTagByValue(value: string): TagConfig | undefined {
  return getAllTags().find(tag => tag.value === value);
}

/**
 * 获取标签颜色
 */
export function getTagColor(value: string): string {
  const tag = findTagByValue(value);
  return tag?.color || '#d9d9d9';
}

/**
 * 验证标签是否有效
 */
export function isValidTag(value: string): boolean {
  return getAllTags().some(tag => tag.value === value);
}

/**
 * 过滤无效标签
 */
export function filterValidTags(tags: string[]): string[] {
  return tags.filter(isValidTag);
}

/**
 * 按分类分组标签
 */
export function groupTagsByCategory(tags: string[]): Record<StrategyTagCategory, string[]> {
  const grouped: any = {
    type: [],
    market: [],
    style: [],
    risk: [],
    indicator: [],
  };

  tags.forEach(tagValue => {
    for (const [category, categoryTags] of Object.entries(STRATEGY_TAGS)) {
      if (categoryTags.some((t: TagConfig) => t.value === tagValue)) {
        grouped[category].push(tagValue);
        break;
      }
    }
  });

  return grouped;
}

/**
 * 获取推荐标签（基于已选标签）
 */
export function getRecommendedTags(selectedTags: string[], limit: number = 5): TagConfig[] {
  const grouped = groupTagsByCategory(selectedTags);
  const recommended: TagConfig[] = [];

  // 如果选了策略类型，推荐相关市场
  if (grouped.type.length > 0) {
    const strategyType = grouped.type[0];

    // CTA策略推荐期货市场
    if (strategyType === 'CTA' && !grouped.market.includes('期货')) {
      const futuresTag = STRATEGY_TAGS.market.find(t => t.value === '期货');
      if (futuresTag) recommended.push(futuresTag);
    }

    // 多因子策略推荐A股
    if (strategyType === '多因子' && !grouped.market.includes('A股')) {
      const aStockTag = STRATEGY_TAGS.market.find(t => t.value === 'A股');
      if (aStockTag) recommended.push(aStockTag);
    }
  }

  // 如果选了市场，推荐常用指标
  if (grouped.market.length > 0 && grouped.indicator.length === 0) {
    recommended.push(...STRATEGY_TAGS.indicator.slice(0, 3));
  }

  return recommended.slice(0, limit);
}

/**
 * 标签搜索（模糊匹配）
 */
export function searchTags(query: string): TagConfig[] {
  const lowerQuery = query.toLowerCase();
  return getAllTags().filter(tag =>
    tag.value.toLowerCase().includes(lowerQuery) ||
    tag.label.toLowerCase().includes(lowerQuery)
  );
}

/**
 * 默认导出
 */
export default {
  STRATEGY_TAG_CATEGORIES,
  STRATEGY_TAGS,
  getAllTags,
  getTagsByCategory,
  findTagByValue,
  getTagColor,
  isValidTag,
  filterValidTags,
  groupTagsByCategory,
  getRecommendedTags,
  searchTags,
};
