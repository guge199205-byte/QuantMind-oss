/**
 * 策略模板匹配算法
 * 根据用户输入的参数智能匹配最适合的策略模板
 */

import {
  StrategyTemplate,
  TemplateMatch,
  TemplateMatchingConfig,
  TemplateSearchFilter,
  TemplateSearchResult,
  TemplateSortOption
} from '../types/template';
import {
  StrategyParams,
  StrategyCategory,
  MarketType,
  Timeframe,
  RiskLevel,
  ComponentType
} from '../types/strategy';
import { STRATEGY_TEMPLATES } from '../data/strategyTemplates';

// ==================== 文本相似度计算 ====================

/**
 * 计算文本相似度（基于Jaccard相似度）
 */
export const calculateTextSimilarity = (text1: string, text2: string): number => {
  if (!text1 || !text2) return 0;

  const words1 = new Set(text1.toLowerCase().split(/\s+/));
  const words2 = new Set(text2.toLowerCase().split(/\s+/));

  const intersection = new Set([...words1].filter(x => words2.has(x)));
  const union = new Set([...words1, ...words2]);

  return intersection.size / union.size;
};

/**
 * 提取文本关键词
 */
export const extractKeywords = (text: string): string[] => {
  if (!text) return [];

  // 移除标点符号并转为小写
  const cleanText = text.toLowerCase().replace(/[^\w\s]/g, ' ');

  // 分词并过滤停用词
  const stopWords = new Set(['的', '是', '在', '和', '有', '我', '你', '他', '它', '我们', '你们', '他们',
                            'this', 'that', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']);

  const words = cleanText.split(/\s+/)
    .filter(word => word.length > 1 && !stopWords.has(word));

  // 统计词频并返回前10个关键词
  const wordCount = new Map<string, number>();
  words.forEach(word => {
    wordCount.set(word, (wordCount.get(word) || 0) + 1);
  });

  return Array.from(wordCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([word]) => word);
};

// ==================== 参数匹配算法 ====================

/**
 * 计算参数匹配度
 */
export const calculateParameterMatch = (
  userParams: StrategyParams,
  templateParams: Partial<StrategyParams>
): number => {
  if (!templateParams) return 0.5; // 默认中等匹配度

  let matches = 0;
  let total = 0;

  const comparableFields = [
    'market', 'timeframe', 'riskLevel', 'style', 'strategyLength', 'backtestPeriod'
  ];

  comparableFields.forEach(field => {
    const userValue = userParams[field as keyof StrategyParams];
    const templateValue = templateParams[field as keyof StrategyParams];

    if (userValue && templateValue) {
      total++;
      if (userValue === templateValue) {
        matches++;
      } else {
        // 部分匹配评分
        if (field === 'riskLevel') {
          // 风险等级相邻级别给予部分分数
          const riskLevels = ['low', 'medium', 'high'];
          const userIndex = riskLevels.indexOf(userValue as string);
          const templateIndex = riskLevels.indexOf(templateValue as string);
          if (Math.abs(userIndex - templateIndex) === 1) {
            matches += 0.5;
          }
        }
      }
    }
  });

  // 数值型参数的相似度计算
  const numericFields = [
    'initialCapital', 'maxDrawdown', 'commissionRate', 'slippage'
  ];

  numericFields.forEach(field => {
    const userValue = userParams[field as keyof StrategyParams] as number;
    const templateValue = templateParams[field as keyof StrategyParams] as number;

    if (userValue && templateValue) {
      total++;
      const similarity = 1 - Math.abs(userValue - templateValue) / Math.max(userValue, templateValue);
      matches += Math.max(0, similarity);
    }
  });

  return total > 0 ? matches / total : 0.5;
};

/**
 * 计算数值参数的适配性
 */
export const calculateParameterFitness = (
  userParams: StrategyParams,
  template: StrategyTemplate
): number => {
  let fitness = 1.0;

  // 资金适配性
  if (userParams.initialCapital && template.minCapital) {
    if (userParams.initialCapital < template.minCapital) {
      fitness *= 0.3; // 资金不足严重降低适配性
    } else if (userParams.initialCapital < template.minCapital * 2) {
      fitness *= 0.8; // 资金刚好满足轻微降低适配性
    }
  }

  // 回撤适配性
  if (userParams.maxDrawdown && template.metadata.performance.maxDrawdown) {
    const templateMaxDD = parseFloat(template.metadata.performance.maxDrawdown);
    if (userParams.maxDrawdown < templateMaxDD * 0.5) {
      fitness *= 0.7; // 用户风险承受能力过低
    }
  }

  // 市场适配性
  if (userParams.market && !template.suitableMarkets.includes(userParams.market as MarketType)) {
    fitness *= 0.5; // 市场不匹配降低适配性
  }

  // 时间框架适配性
  if (userParams.timeframe && !template.suitableTimeframes.includes(userParams.timeframe as Timeframe)) {
    fitness *= 0.6; // 时间框架不匹配降低适配性
  }

  // 风险等级适配性
  if (userParams.riskLevel && !template.suitableRiskLevels.includes(userParams.riskLevel as RiskLevel)) {
    fitness *= 0.4; // 风险等级不匹配严重降低适配性
  }

  return fitness;
};

// ==================== 标签和关键词匹配 ====================

/**
 * 计算标签匹配度
 */
export const calculateTagMatch = (
  userKeywords: string[],
  templateTags: string[]
): number => {
  if (!userKeywords.length || !templateTags.length) return 0;

  const userTagSet = new Set(userKeywords.map(tag => tag.toLowerCase()));
  const templateTagSet = new Set(templateTags.map(tag => tag.toLowerCase()));

  const intersection = new Set([...userTagSet].filter(tag => templateTagSet.has(tag)));
  const union = new Set([...userTagSet, ...templateTagSet]);

  return intersection.size / union.size;
};

/**
 * 从用户描述中提取意图关键词
 */
export const extractIntentKeywords = (description: string): string[] => {
  if (!description) return [];

  const keywords = extractKeywords(description);

  // 扩展同义词
  const synonyms = new Map([
    ['趋势', ['trend', 'trending', 'uptrend', 'downtrend']],
    ['均值', ['mean', 'average', 'reversion']],
    ['动量', ['momentum', 'momentum']],
    ['突破', ['breakout', 'break', 'resistance']],
    ['套利', ['arbitrage', 'pair', 'spread']],
    ['均线', ['ma', 'moving', 'average']],
    ['网格', ['grid', 'range']],
    ['波动', ['volatility', 'vol', 'atr']],
    ['配对', ['pair', 'pairs', 'correlation']],
    ['选股', ['selection', 'stock', 'factor']],
    ['价值', ['value', 'valuation', 'fundamental']],
    ['成长', ['growth', 'growing']],
    ['质量', ['quality', 'profitability']],
  ]);

  const expandedKeywords = [...keywords];

  keywords.forEach(keyword => {
    const synonymList = synonyms.get(keyword);
    if (synonymList) {
      expandedKeywords.push(...synonymList);
    }
  });

  return [...new Set(expandedKeywords)];
};

// ==================== 组件匹配分析 ====================

/**
 * 分析用户所需的策略组件
 */
export const analyzeRequiredComponents = (description: string, params: StrategyParams): ComponentType[] => {
  const components: ComponentType[] = [];
  const desc = description.toLowerCase();

  // 必需的基础组件
  components.push('DATA_HANDLING');
  components.push('LOGIC');
  components.push('RISK_CONTROL');

  // 根据描述判断是否需要优化组件
  if (desc.includes('优化') || desc.includes('performance') || desc.includes('回测')) {
    components.push('OPTIMIZATION');
  }

  // 根据风险等级判断组件复杂度
  if (params.riskLevel === 'high') {
    // 高风险策略需要更复杂的风险控制
    components.push('RISK_CONTROL');
  }

  // 根据策略类型判断特殊需求
  if (desc.includes('机器学习') || desc.includes('ml') || desc.includes('ai')) {
    components.push('OPTIMIZATION');
  }

  return [...new Set(components)];
};

/**
 * 计算组件匹配度
 */
export const calculateComponentMatch = (
  requiredComponents: ComponentType[],
  templateComponents: any[]
): number => {
  if (!requiredComponents.length || !templateComponents.length) return 0.5;

  const templateComponentTypes = templateComponents.map(comp => comp.type);

  let matches = 0;
  requiredComponents.forEach(comp => {
    if (templateComponentTypes.includes(comp)) {
      matches++;
    }
  });

  return matches / requiredComponents.length;
};

// ==================== 主匹配算法 ====================

/**
 * 默认匹配配置
 */
export const DEFAULT_MATCHING_CONFIG: TemplateMatchingConfig = {
  weights: {
    category: 0.2,        // 策略类别权重
    description: 0.25,    // 描述相似度权重
    parameters: 0.2,      // 参数匹配权重
    riskLevel: 0.15,      // 风险等级权重
    market: 0.1,          // 市场适配权重
    timeframe: 0.1        // 时间框架权重
  },
  thresholds: {
    minConfidence: 0.3,   // 最低置信度阈值
    maxResults: 5         // 最大返回结果数
  }
};

/**
 * 策略模板匹配器
 */
export class TemplateMatcher {
  private config: TemplateMatchingConfig;

  constructor(config: TemplateMatchingConfig = DEFAULT_MATCHING_CONFIG) {
    this.config = config;
  }

  /**
   * 执行模板匹配
   */
  async matchTemplates(
    userParams: StrategyParams,
    userDescription?: string
  ): Promise<TemplateMatch[]> {
    const userKeywords = userDescription ? extractIntentKeywords(userDescription) : [];
    const requiredComponents = userDescription ? analyzeRequiredComponents(userDescription, userParams) : [];

    const matches: TemplateMatch[] = [];

    for (const template of STRATEGY_TEMPLATES) {
      const match = await this.calculateTemplateMatch(
        template,
        userParams,
        userDescription,
        userKeywords,
        requiredComponents
      );

      if (match.confidence >= this.config.thresholds.minConfidence) {
        matches.push(match);
      }
    }

    // 按置信度排序并返回前N个结果
    return matches
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, this.config.thresholds.maxResults);
  }

  /**
   * 计算单个模板的匹配度
   */
  private async calculateTemplateMatch(
    template: StrategyTemplate,
    userParams: StrategyParams,
    userDescription?: string,
    userKeywords: string[] = [],
    requiredComponents: ComponentType[] = []
  ): Promise<TemplateMatch> {
    const weights = this.config.weights;

    // 1. 类别匹配度
    const categoryScore = this.calculateCategoryScore(userParams, template);

    // 2. 描述相似度
    const descriptionScore = userDescription ?
      calculateTextSimilarity(userDescription, template.description) : 0.5;

    // 3. 参数匹配度
    const parameterScore = calculateParameterMatch(userParams, template.defaultParameters);

    // 4. 参数适配性
    const fitnessScore = calculateParameterFitness(userParams, template);

    // 5. 风险等级匹配度
    const riskLevelScore = this.calculateRiskLevelScore(userParams, template);

    // 6. 市场适配度
    const marketScore = this.calculateMarketScore(userParams, template);

    // 7. 时间框架适配度
    const timeframeScore = this.calculateTimeframeScore(userParams, template);

    // 8. 标签匹配度
    const tagScore = calculateTagMatch(userKeywords, template.tags);

    // 9. 组件匹配度
    const componentScore = calculateComponentMatch(requiredComponents, template.requiredComponents);

    // 计算综合得分
    const score =
      categoryScore * weights.category +
      descriptionScore * weights.description +
      parameterScore * weights.parameters * 0.6 +
      fitnessScore * weights.parameters * 0.4 +
      riskLevelScore * weights.riskLevel +
      marketScore * weights.market +
      timeframeScore * weights.timeframe;

    // 计算置信度（综合多个因素）
    const confidence = Math.min(1.0, score * 1.2 + tagScore * 0.2 + componentScore * 0.1);

    // 生成匹配原因
    const reasons = this.generateMatchReasons(
      template,
      categoryScore,
      descriptionScore,
      parameterScore,
      riskLevelScore,
      marketScore,
      timeframeScore,
      tagScore
    );

    // 生成适配建议
    const adaptations = this.generateAdaptations(template, userParams);

    return {
      template,
      confidence,
      reason: reasons.join('; '),
      adaptations,
      score,
      matchFactors: {
        category: categoryScore,
        description: descriptionScore,
        parameters: parameterScore,
        riskLevel: riskLevelScore
      }
    };
  }

  /**
   * 计算类别得分
   */
  private calculateCategoryScore(userParams: StrategyParams, template: StrategyTemplate): number {
    if (!userParams.style) return 0.5;

    const categoryMap: Record<string, StrategyCategory> = {
      'conservative': 'trend',
      'balanced': 'mean_reversion',
      'aggressive': 'momentum',
      'custom': 'trend'
    };

    const expectedCategory = categoryMap[userParams.style];
    return expectedCategory === template.category ? 1.0 : 0.3;
  }

  /**
   * 计算风险等级得分
   */
  private calculateRiskLevelScore(userParams: StrategyParams, template: StrategyTemplate): number {
    if (!userParams.riskLevel) return 0.5;

    if (template.suitableRiskLevels.includes(userParams.riskLevel as RiskLevel)) {
      return 1.0;
    }

    // 邻近风险等级给予部分分数
    const riskLevels = ['low', 'medium', 'high'];
    const userIndex = riskLevels.indexOf(userParams.riskLevel);

    for (const templateRisk of template.suitableRiskLevels) {
      const templateIndex = riskLevels.indexOf(templateRisk);
      if (Math.abs(userIndex - templateIndex) === 1) {
        return 0.6;
      }
    }

    return 0.2;
  }

  /**
   * 计算市场适配得分
   */
  private calculateMarketScore(userParams: StrategyParams, template: StrategyTemplate): number {
    if (!userParams.market) return 0.5;

    return template.suitableMarkets.includes(userParams.market as MarketType) ? 1.0 : 0.3;
  }

  /**
   * 计算时间框架适配得分
   */
  private calculateTimeframeScore(userParams: StrategyParams, template: StrategyTemplate): number {
    if (!userParams.timeframe) return 0.5;

    return template.suitableTimeframes.includes(userParams.timeframe as Timeframe) ? 1.0 : 0.4;
  }

  /**
   * 生成匹配原因
   */
  private generateMatchReasons(
    template: StrategyTemplate,
    categoryScore: number,
    descriptionScore: number,
    parameterScore: number,
    riskLevelScore: number,
    marketScore: number,
    timeframeScore: number,
    tagScore: number
  ): string[] {
    const reasons: string[] = [];

    if (categoryScore >= 0.8) {
      reasons.push(`策略类型匹配（${template.category}）`);
    }

    if (descriptionScore >= 0.7) {
      reasons.push('描述高度相关');
    }

    if (parameterScore >= 0.7) {
      reasons.push('参数配置匹配');
    }

    if (riskLevelScore >= 0.8) {
      reasons.push('风险等级适配');
    }

    if (marketScore >= 0.8) {
      reasons.push('市场环境适配');
    }

    if (timeframeScore >= 0.8) {
      reasons.push('时间框架适配');
    }

    if (tagScore >= 0.5) {
      reasons.push('标签匹配度高');
    }

    if (reasons.length === 0) {
      reasons.push('基础匹配度达标');
    }

    return reasons;
  }

  /**
   * 生成适配建议
   */
  private generateAdaptations(template: StrategyTemplate, userParams: StrategyParams): string[] {
    const adaptations: string[] = [];

    // 资金调整建议
    if (userParams.initialCapital && userParams.initialCapital < template.minCapital) {
      adaptations.push(`建议增加初始资金至${template.minCapital}元以上`);
    }

    // 参数调整建议
    if (template.metadata.complexity === 'high' && userParams.riskLevel === 'low') {
      adaptations.push('建议降低策略复杂度或提高风险承受能力');
    }

    if (template.metadata.complexity === 'low' && userParams.riskLevel === 'high') {
      adaptations.push('建议选择更复杂的策略以满足高风险偏好');
    }

    // 市场调整建议
    if (userParams.market && !template.suitableMarkets.includes(userParams.market as MarketType)) {
      adaptations.push(`建议切换到适合的市场：${template.suitableMarkets.join(', ')}`);
    }

    // 时间框架调整建议
    if (userParams.timeframe && !template.suitableTimeframes.includes(userParams.timeframe as Timeframe)) {
      adaptations.push(`建议调整时间框架为：${template.suitableTimeframes.join(', ')}`);
    }

    return adaptations;
  }
}

// ==================== 模板搜索功能 ====================

/**
 * 模板搜索器
 */
export class TemplateSearcher {
  /**
   * 搜索策略模板
   */
  static searchTemplates(
    query?: string,
    filter?: TemplateSearchFilter,
    sortBy: TemplateSortOption = 'name',
    page: number = 1,
    pageSize: number = 10
  ): TemplateSearchResult {
    let filteredTemplates = [...STRATEGY_TEMPLATES];

    // 文本搜索
    if (query) {
      const searchTerms = query.toLowerCase().split(/\s+/);
      filteredTemplates = filteredTemplates.filter(template => {
        const searchText = [
          template.name,
          template.description,
          ...template.tags,
          template.category,
          template.author
        ].join(' ').toLowerCase();

        return searchTerms.every(term => searchText.includes(term));
      });
    }

    // 应用过滤器
    if (filter) {
      if (filter.category) {
        filteredTemplates = filteredTemplates.filter(t => t.category === filter.category);
      }

      if (filter.riskLevel) {
        filteredTemplates = filteredTemplates.filter(t =>
          t.suitableRiskLevels.includes(filter.riskLevel!)
        );
      }

      if (filter.market) {
        filteredTemplates = filteredTemplates.filter(t =>
          t.suitableMarkets.includes(filter.market!)
        );
      }

      if (filter.timeframe) {
        filteredTemplates = filteredTemplates.filter(t =>
          t.suitableTimeframes.includes(filter.timeframe!)
        );
      }

      if (filter.tags && filter.tags.length > 0) {
        filteredTemplates = filteredTemplates.filter(t =>
          filter.tags!.some(tag => t.tags.includes(tag))
        );
      }

      if (filter.minCapital) {
        filteredTemplates = filteredTemplates.filter(t => t.minCapital <= filter.minCapital!);
      }

      if (filter.maxSymbols) {
        filteredTemplates = filteredTemplates.filter(t => t.maxSymbols <= filter.maxSymbols!);
      }

      if (filter.complexity) {
        filteredTemplates = filteredTemplates.filter(t =>
          t.metadata.complexity === filter.complexity
        );
      }
    }

    // 排序
    filteredTemplates = this.sortTemplates(filteredTemplates, sortBy);

    // 分页
    const total = filteredTemplates.length;
    const totalPages = Math.ceil(total / pageSize);
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const templates = filteredTemplates.slice(startIndex, endIndex);

    return {
      templates,
      total,
      page,
      pageSize,
      totalPages,
      filters: filter || {},
      sort: sortBy,
      searchTime: Date.now()
    };
  }

  /**
   * 模板排序
   */
  private static sortTemplates(
    templates: StrategyTemplate[],
    sortBy: TemplateSortOption
  ): StrategyTemplate[] {
    switch (sortBy) {
      case 'name':
        return templates.sort((a, b) => a.name.localeCompare(b.name));

      case 'createdAt':
        return templates.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

      case 'popularity':
        // 简单的受欢迎度排序（基于复杂度和标签数量）
        return templates.sort((a, b) => {
          const scoreA = a.tags.length + (a.metadata.complexity === 'low' ? 1 : 0);
          const scoreB = b.tags.length + (b.metadata.complexity === 'low' ? 1 : 0);
          return scoreB - scoreA;
        });

      case 'rating':
        // 基于预期收益的评分排序
        return templates.sort((a, b) => {
          const getExpectedReturn = (template: StrategyTemplate) => {
            const returnStr = template.metadata.performance.expectedReturn;
            const match = returnStr.match(/(\d+)%/);
            return match ? parseInt(match[1]) : 0;
          };
          return getExpectedReturn(b) - getExpectedReturn(a);
        });

      case 'complexity':
        const complexityOrder = { 'low': 1, 'medium': 2, 'high': 3 };
        return templates.sort((a, b) =>
          complexityOrder[a.metadata.complexity] - complexityOrder[b.metadata.complexity]
        );

      case 'successRate':
        // 基于夏普比率的成功率排序
        return templates.sort((a, b) => {
          const getSharpeRatio = (template: StrategyTemplate) => {
            const ratioStr = template.metadata.performance.sharpeRatio;
            const match = ratioStr.match(/([\d.]+)/);
            return match ? parseFloat(match[1]) : 0;
          };
          return getSharpeRatio(b) - getSharpeRatio(a);
        });

      default:
        return templates;
    }
  }
}

// ==================== 导出 ====================

export const templateMatcher = new TemplateMatcher();
