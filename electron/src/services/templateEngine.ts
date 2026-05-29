/**
 * 策略模板引擎
 * 负责模板匹配、代码生成和模板管理
 */

import {
  StrategyTemplate,
  ComponentType,
  StrategyParams,
  MarketType,
  Timeframe,
  RiskLevel,
  StrategyComponent
} from '../types/strategy';

import {
  TemplateMatch,
  TemplateMatchingConfig,
  StrategyGenerationRequest,
  StrategyGenerationResult,
  ComponentCodeTemplate,
  TemplatePlaceholder,
  TemplateLibrary,
  TemplateValidationResult,
  GenerationStage,
  GeneratedComponent,
  TemplateValidationError,
  TemplateValidationWarning
} from '../types/template';

export class TemplateEngine {
  private templates: Map<string, StrategyTemplate> = new Map();
  private components: Map<string, StrategyComponent> = new Map();
  private codeTemplates: Map<string, ComponentCodeTemplate> = new Map();
  private matchingConfig: TemplateMatchingConfig;

  constructor() {
    this.matchingConfig = {
      weights: {
        category: 0.3,
        description: 0.25,
        parameters: 0.2,
        riskLevel: 0.15,
        market: 0.05,
        timeframe: 0.05
      },
      thresholds: {
        minConfidence: 0.6,
        maxResults: 5
      }
    };

    this.initializeDefaultComponents();
    this.initializeDefaultCodeTemplates();
  }

  /**
   * 加载模板库
   */
  async loadTemplateLibrary(library: TemplateLibrary): Promise<void> {
    this.templates.clear();
    this.components.clear();

    // 加载模板
    library.templates.forEach(template => {
      this.templates.set(template.id, template);
    });

    // 加载组件
    library.components.forEach(component => {
      // 使用 component.type 作为 key（component 可能不包含 id）
      this.components.set(component.type as any, component);
    });

    console.log(`已加载 ${library.templates.length} 个模板和 ${library.components.length} 个组件`);
  }

  /**
   * 匹配最适合的模板
   */
  async matchTemplate(params: StrategyParams): Promise<TemplateMatch[]> {
    const matches: TemplateMatch[] = [];

    for (const template of this.templates.values()) {
      const match = await this.calculateTemplateMatch(template, params);
      if (match.confidence >= this.matchingConfig.thresholds.minConfidence) {
        matches.push(match);
      }
    }

    // 按评分排序
    matches.sort((a, b) => b.score - a.score);

    return matches.slice(0, this.matchingConfig.thresholds.maxResults);
  }

  /**
   * 计算模板匹配度
   */
  private async calculateTemplateMatch(
    template: StrategyTemplate,
    params: StrategyParams
  ): Promise<TemplateMatch> {
    const factors = {
      category: this.calculateCategoryMatch(template, params),
      description: this.calculateDescriptionMatch(template, params),
      parameters: this.calculateParameterMatch(template, params),
      riskLevel: this.calculateRiskLevelMatch(template, params),
      market: this.calculateMarketMatch(template, params),
      timeframe: this.calculateTimeframeMatch(template, params)
    };

    // 计算总分
    const score = Object.entries(factors).reduce(
      (total, [key, value]) => total + value * this.matchingConfig.weights[key as keyof typeof factors],
      0
    );

    // 计算置信度
    const confidence = Math.min(score, 1.0);

    // 生成适配建议
    const adaptations = this.generateAdaptations(template, params);

    // 生成匹配原因
    const reason = this.generateMatchReason(template, params, factors);

    return {
      template,
      confidence,
      reason,
      adaptations,
      score,
      matchFactors: factors
    };
  }

  /**
   * 计算类别匹配度
   */
  private calculateCategoryMatch(template: StrategyTemplate, params: StrategyParams): number {
    // 这里可以根据用户描述智能推断类别
    // 简化实现：基于关键词匹配
    const categoryKeywords = {
      trend: ['趋势', '突破', '动量', '上涨', '下跌', '通道', '均线'],
      mean_reversion: ['回归', '均值', '反转', '超买', '超卖', '震荡'],
      momentum: ['动量', '突破', '加速', '惯性', '强势', '弱势'],
      breakout: ['突破', '阻力', '支撑', '区间', '通道', '横盘'],
      arbitrage: ['套利', '价差', '对冲', '跨市场', '统计套利']
    };

    const description = params.description.toLowerCase();
    let maxScore = 0;

    for (const [category, keywords] of Object.entries(categoryKeywords)) {
      const score = keywords.reduce((count, keyword) => {
        return count + (description.includes(keyword) ? 1 : 0);
      }, 0);

      if (category === template.category && score > 0) {
        maxScore = Math.max(maxScore, score / keywords.length);
      }
    }

    return maxScore;
  }

  /**
   * 计算描述匹配度
   */
  private calculateDescriptionMatch(template: StrategyTemplate, params: StrategyParams): number {
    const description = params.description.toLowerCase();
    const templateDesc = template.description.toLowerCase();

    // 简单的文本相似度计算
    const commonWords = this.getCommonWords(description, templateDesc);
    const similarity = commonWords.length / Math.max(description.split(' ').length, templateDesc.split(' ').length);

    return similarity;
  }

  private getCommonWords(a: string, b: string): string[] {
    const sa = a.split(/\s+/).map(s => s.trim()).filter(Boolean);
    const sb = b.split(/\s+/).map(s => s.trim()).filter(Boolean);
    const setB = new Set(sb);
    return sa.filter(w => setB.has(w));
  }

  /**
   * 计算参数匹配度
   */
  private calculateParameterMatch(template: StrategyTemplate, params: StrategyParams): number {
    let score = 0;
    let totalChecks = 0;

    // 检查关键参数匹配
    const paramChecks = [
      { template: template.suitableMarkets, actual: params.market, weight: 1 },
      { template: template.suitableTimeframes, actual: params.timeframe, weight: 1 },
      { template: template.suitableRiskLevels, actual: params.riskLevel, weight: 1 },
      { template: template.maxSymbols, actual: params.symbols.length, weight: 1, compare: (t, a) => a <= t },
      { template: template.minCapital, actual: params.initialCapital, weight: 1, compare: (t, a) => a >= t }
    ];

    paramChecks.forEach(({ template: templateValues, actual, weight, compare }) => {
      totalChecks += weight;
      if (Array.isArray(templateValues) && (templateValues as any).includes(actual as any)) {
        score += weight;
      } else if (typeof templateValues === 'number' && compare) {
        // 比如 maxSymbols/minCapital 使用数字比较
        if (compare(templateValues as any, actual as any)) score += weight * 0.75;
      } else if (compare && Array.isArray(templateValues) && templateValues.length > 0) {
        // 退化比较：尝试用第一个元素进行比较
        if (compare((templateValues as any)[0], actual)) score += weight * 0.5;
      }
    });

    return totalChecks > 0 ? score / totalChecks : 0;
  }

  /**
   * 计算风险等级匹配度
   */
  private calculateRiskLevelMatch(template: StrategyTemplate, params: StrategyParams): number {
    if (template.suitableRiskLevels.includes(params.riskLevel)) {
      return 1.0;
    }

    // 风险等级兼容性矩阵
    const compatibility: Record<RiskLevel, Record<RiskLevel, number>> = {
      low: { low: 1.0, medium: 0.8, high: 0.5 },
      medium: { low: 0.8, medium: 1.0, high: 0.8 },
      high: { low: 0.5, medium: 0.8, high: 1.0 }
    };

    return compatibility[template.suitableRiskLevels[0]]?.[params.riskLevel] || 0;
  }

  /**
   * 计算市场匹配度
   */
  private calculateMarketMatch(template: StrategyTemplate, params: StrategyParams): number {
    if (template.suitableMarkets.includes(params.market)) {
      return 1.0;
    }

    // 市场兼容性检查
    const compatibility: Record<MarketType, Record<MarketType, number>> = {
      CN: { CN: 1.0, US: 0.3, HK: 0.5, GLOBAL: 0.2 },
      US: { CN: 0.3, US: 1.0, HK: 0.6, GLOBAL: 0.4 },
      HK: { CN: 0.5, US: 0.6, HK: 1.0, GLOBAL: 0.3 },
      GLOBAL: { CN: 0.2, US: 0.4, HK: 0.3, GLOBAL: 1.0 }
    };

    return compatibility[template.suitableMarkets[0]]?.[params.market] || 0;
  }

  /**
   * 计算时间框架匹配度
   */
  private calculateTimeframeMatch(template: StrategyTemplate, params: StrategyParams): number {
    if (template.suitableTimeframes.includes(params.timeframe)) {
      return 1.0;
    }

    // 时间框架兼容性检查
    const compatibility: Partial<Record<Timeframe, Partial<Record<Timeframe, number>>>> = {
      '1m': { '1m': 1.0, '5m': 0.8, '15m': 0.6, '30m': 0.5, '1h': 0.3, '4h': 0.2, '1d': 0.1 },
      '5m': { '1m': 0.9, '5m': 1.0, '15m': 0.8, '30m': 0.7, '1h': 0.5, '4h': 0.3, '1d': 0.2 },
      '15m': { '1m': 0.7, '5m': 0.9, '15m': 1.0, '30m': 0.9, '1h': 0.7, '4h': 0.5, '1d': 0.3 },
      '30m': { '1m': 0.5, '5m': 0.7, '15m': 0.9, '30m': 1.0, '1h': 0.8, '4h': 0.6, '1d': 0.4 },
      '1h': { '1m': 0.3, '5m': 0.5, '15m': 0.7, '30m': 0.8, '1h': 1.0, '4h': 0.8, '1d': 0.6 },
      '4h': { '1m': 0.2, '5m': 0.3, '15m': 0.5, '30m': 0.6, '1h': 0.8, '4h': 1.0, '1d': 0.8 },
      '1d': { '1m': 0.1, '5m': 0.2, '15m': 0.3, '30m': 0.4, '1h': 0.6, '4h': 0.8, '1d': 1.0 },
      '1w': { '1m': 0.1, '5m': 0.1, '15m': 0.2, '30m': 0.3, '1h': 0.4, '4h': 0.6, '1d': 0.8 },
      '1M': { '1m': 0.05, '5m': 0.05, '15m': 0.1, '30m': 0.15, '1h': 0.2, '4h': 0.3, '1d': 0.5 }
    };

    return compatibility[template.suitableTimeframes[0]]?.[params.timeframe] || 0;
  }

  /**
   * 生成适配建议
   */
  private generateAdaptations(template: StrategyTemplate, params: StrategyParams): string[] {
    const adaptations: string[] = [];

    // 检查参数差异
    if (!template.suitableMarkets.includes(params.market)) {
      adaptations.push(`模板主要适用于${template.suitableMarkets.join('、')}，当前选择${params.market}可能需要调整`);
    }

    if (!template.suitableTimeframes.includes(params.timeframe)) {
      adaptations.push(`推荐使用${template.suitableTimeframes.join('或')}时间框架`);
    }

    if (params.symbols.length > template.maxSymbols) {
      adaptations.push(`模板最大支持${template.maxSymbols}只股票，当前有${params.symbols.length}只`);
    }

    if (params.initialCapital < template.minCapital) {
      adaptations.push(`模板建议最低资金${template.minCapital}元，当前为${params.initialCapital}元`);
    }

    return adaptations;
  }

  /**
   * 生成匹配原因
   */
  private generateMatchReason(
    template: StrategyTemplate,
    params: StrategyParams,
    factors: Record<string, number>
  ): string {
    const reasons: string[] = [];

    if (factors.category > 0.5) {
      reasons.push(`策略类型高度匹配${template.category}策略`);
    }

    if (factors.description > 0.3) {
      reasons.push('策略描述与模板高度相关');
    }

    if (factors.parameters > 0.7) {
      reasons.push('参数配置完全符合模板要求');
    }

    if (factors.riskLevel > 0.8) {
      reasons.push(`风险等级${params.riskLevel}与模板匹配度高`);
    }

    if (factors.market > 0.8) {
      reasons.push(`市场${params.market}与模板完美匹配`);
    }

    if (factors.timeframe > 0.8) {
      reasons.push(`时间框架${params.timeframe}非常适合`);
    }

    return reasons.length > 0 ? reasons.join('；') : '模板匹配成功';
  }

  /**
   * 生成策略代码
   */
  async generateStrategy(request: StrategyGenerationRequest): Promise<StrategyGenerationResult> {
    try {
      const templateMatch = request.template || (await this.matchTemplate(request.userParams))[0];

      if (!templateMatch) {
        throw new Error('未找到匹配的策略模板');
      }

      const template = 'template' in templateMatch ? templateMatch.template : templateMatch;

      // 定义生成阶段
      const stages: GenerationStage[] = [
        { name: 'framework', type: 'framework', order: 1, required: true, dependencies: [] },
        { name: 'imports', type: 'imports', order: 2, required: true, dependencies: [] },
        { name: 'data_handling', type: 'data_handling', order: 3, required: true, dependencies: [] },
        { name: 'logic', type: 'logic', order: 4, required: true, dependencies: ['data_handling'] },
        { name: 'risk_control', type: 'risk_control', order: 5, required: true, dependencies: ['logic'] },
        { name: 'optimization', type: 'optimization', order: 6, required: false, dependencies: ['logic'] }
      ];

      // 合并用户自定义组件
      const allComponents = [...template.requiredComponents];
      if (request.customComponents) {
        allComponents.push(...request.customComponents);
      }

      // 按阶段生成代码
      const generatedComponents: GeneratedComponent[] = [];
      let fullCode = '';

      for (const stage of stages.sort((a, b) => a.order - b.order)) {
        if (stage.required || this.shouldGenerateStage(stage, request.userParams)) {
          const compType = this.mapStageToComponentType(stage.type as any);
          const component = await this.generateComponent(
            compType,
            template,
            request.userParams,
            request
          );

          if (component) {
            generatedComponents.push(component);
            fullCode += component.code + '\n\n';
          }
        }
      }

      // 后处理代码
      const processedCode = this.postProcessCode(fullCode, request);

      // 验证生成的代码
      const validation = await this.validateGeneratedCode(processedCode, template);

      return {
        success: validation.isValid,
        template,
        strategy: {
          code: processedCode,
          parameters: request.userParams,
          components: generatedComponents,
          metadata: {
            generationTime: Date.now(),
            templateId: template.id,
            customizations: []
          }
        },
        errors: validation.errors.map(e => e.message),
        warnings: validation.warnings.map(w => w.message),
        suggestions: validation.suggestions
      };

    } catch (error) {
      return {
        success: false,
        errors: [`生成失败: ${error instanceof Error ? error.message : String(error)}`],
        warnings: [],
        suggestions: []
      };
    }
  }

  /**
   * 判断是否应该生成某个阶段
   */
  private shouldGenerateStage(stage: GenerationStage, params: StrategyParams): boolean {
    // 基础阶段总是生成
    if (stage.required) return true;

    // 优化阶段根据参数决定
    if (stage.type === 'optimization') {
      return params.style === 'aggressive' || params.riskLevel === 'high';
    }

    return false;
  }

  /**
   * 生成组件代码
   */
  private async generateComponent(
    type: ComponentType,
    template: StrategyTemplate,
    params: StrategyParams,
    _request: StrategyGenerationRequest
  ): Promise<GeneratedComponent | null> {
    const component = template.requiredComponents.find(c => c.type === type);
    if (!component) {
      return null;
    }

    try {
      // 获取代码模板
      const codeTemplate = this.getComponentCodeTemplate(component.type);

      if (!codeTemplate) {
        return null;
      }

      // 填充模板参数
      const filledCode = this.fillTemplate(codeTemplate, params, template);

      // 简单的组件代码验证（因为validateComponentCode方法不存在）
      const validation = {
        isValid: true,
        errors: [],
        warnings: [],
        suggestions: []
      };

      return {
        type: component.type,
        name: component.name,
        code: filledCode,
        parameters: this.extractParameters(params, component),
        validation
      };

    } catch (error) {
      console.error(`生成${type}组件失败:`, error);
      return null;
    }
  }

  /**
   * 填充模板占位符
   */
  private fillTemplate(
    template: ComponentCodeTemplate,
    params: StrategyParams,
    strategyTemplate: StrategyTemplate
  ): string {
    let code = template.codeTemplate;

    // 填充占位符
    template.placeholders.forEach(placeholder => {
      const value = this.getPlaceholderValue(placeholder, params, strategyTemplate);
      code = code.replace(
        new RegExp(`\\$\\{${placeholder.name}\\}`, 'g'),
        String(value)
      );
    });

    return code;
  }

  /**
   * 获取占位符值
   */
  private getPlaceholderValue(
    placeholder: TemplatePlaceholder,
    params: StrategyParams,
    template: StrategyTemplate
  ): any {
    // 尝试从参数映射中获取值
    const mapping = this.getParameterMapping(template);
    if (mapping[placeholder.name]) {
      return this.resolveParameter(mapping[placeholder.name], params);
    }

    // 使用默认值
    return placeholder.defaultValue;
  }

  /**
   * 解析参数值
   */
  private resolveParameter(mapping: any, params: StrategyParams): any {
    if (typeof mapping === 'string') {
      return this.getNestedValue(params, mapping);
    }
    return mapping;
  }

  /**
   * 获取嵌套对象值
   */
  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  /**
   * 将生成阶段类型映射到组件类型
   */
  private mapStageToComponentType(stageType: string): ComponentType {
    switch (stageType) {
      case 'framework':
        return 'ENTRY';
      case 'imports':
      case 'data_handling':
        return 'DATA_HANDLING';
      case 'logic':
        return 'LOGIC';
      case 'risk_control':
        return 'RISK_CONTROL';
      case 'optimization':
        return 'OPTIMIZATION';
      default:
        return 'LOGIC';
    }
  }

  /**
   * 后处理代码
   */
  private postProcessCode(code: string, request: StrategyGenerationRequest): string {
    let processedCode = code;

    // 添加注释
    if (request.generationConfig.includeComments) {
      processedCode = this.addCodeComments(processedCode);
    }

    // 添加日志
    if (request.generationConfig.includeLogging) {
      processedCode = this.addLoggingCode(processedCode);
    }

    // 添加错误处理
    if (request.generationConfig.includeErrorHandling) {
      processedCode = this.addErrorHandling(processedCode);
    }

    // 添加性能优化
    if (request.generationConfig.includePerformanceOptimization) {
      processedCode = this.addPerformanceOptimization(processedCode);
    }

    return processedCode;
  }

  /**
   * 添加代码注释
   */
  private addCodeComments(code: string): string {
    const comments = `"""
# -*- coding: utf-8 -*-
"""
QuantMind策略模板生成
生成时间: ${new Date().toLocaleString()}
使用模板: 基础模板
"""

# 策略说明
# 此策略由AI基于模板生成，请仔细验证后使用

# 免责声明
# 本策略仅供学习和研究使用，不构成投资建议

# 风险提示
# 策略存在风险，请充分理解后再使用
`;

    return comments + '\n' + code;
  }

  /**
   * 添加日志代码
   */
  private addLoggingCode(code: string): string {
    const loggingCode = `
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

`;

    return loggingCode + '\n' + code;
  }

  /**
   * 添加错误处理
   */
  private addErrorHandling(code: string): string {
    const errorHandling = `
# 错误处理
try:
    # 策略主要逻辑
    pass
except Exception as e:
    logger.error(f"策略执行错误: {e}")
    # 错误处理逻辑
    pass
finally:
    # 清理资源
    pass
`;

    return code.replace(/\ntry:/g, errorHandling.replace(/\nexcept:/g, '\ntry:').replace(/\nfinally:/g, '\nfinally:'));
  }

  /**
   * 添加性能优化
   */
  private addPerformanceOptimization(code: string): string {
    const performanceOptimization = `
# 性能优化提示
# 1. 避免在循环中重复计算
# 2. 使用向量化操作替代循环
# 3. 合理使用缓存
# 4. 及时释放不需要的资源
`;

    return code + performanceOptimization;
  }

  /**
   * 验证生成的代码
   */
  private async validateGeneratedCode(code: string, template: StrategyTemplate): Promise<TemplateValidationResult> {
    // 这里可以集成代码处理器进行验证
    // 简化实现，只做基础检查
    const errors: string[] = [];
    const warnings: string[] = [];
    const suggestions: string[] = [];

    // 基础语法检查
    if (!code.includes('def initialize')) {
      errors.push('缺少必需的initialize函数');
    }

    if (!code.includes('def handle_data')) {
      errors.push('缺少必需的handle_data函数');
    }

    // 检查必需组件
    const requiredComponents = template.requiredComponents.map(c => c.type);
    for (const component of requiredComponents) {
      if (!this.hasComponentType(code, component)) {
        errors.push(`缺少${component}组件`);
      }
    }

    // 基础质量检查
    if (!code.includes('g.benchmark')) {
      warnings.push('建议设置基准');
    }

    if (!code.includes('order') && !code.includes('target')) {
      warnings.push('策略中未发现交易逻辑');
    }

    return {
      isValid: errors.length === 0,
      errors: errors.map(e => ({
        component: 'general',
        field: 'syntax',
        message: e,
        severity: 'error'
      })),
      warnings: warnings.map(w => ({
        component: 'general',
        field: 'quality',
        message: w,
        suggestion: '建议改进代码质量'
      })),
      suggestions,
      score: errors.length === 0 ? 100 : Math.max(0, 100 - errors.length * 20)
    };
  }

  /**
   * 检查代码中是否包含特定组件类型
   */
  private hasComponentType(code: string, type: ComponentType): boolean {
    const componentPatterns: Record<ComponentType, RegExp> = {
      ENTRY: /def.*entry|买入|开仓/i,
      EXIT: /def.*exit|卖出|平仓/i,
      RISK: /止损|止盈|风险控制/i,
      DATA_HANDLING: /attribute_history|get.*data|数据/i,
      LOGIC: /if|for|while|逻辑|signal/i,
      RISK_CONTROL: /止损|风控|risk/i,
      OPTIMIZATION: /optimize|grid_search|bayesian/i
    } as any;

    const pattern = componentPatterns[type as ComponentType];
    return pattern ? pattern.test(code) : false;
  }

  /**
   * 获取组件参数
   */
  private extractParameters(params: StrategyParams, component: StrategyComponent): Record<string, any> {
    const parameters: Record<string, any> = {};

    // 提取相关参数
    if (component.type === 'RISK' || component.type === 'RISK_CONTROL') {
      parameters.stopLoss = params.stopLoss;
      parameters.takeProfit = params.takeProfit;
      parameters.positionSize = params.positionSize;
      parameters.maxPositions = params.maxPositions;
      parameters.maxDrawdown = params.maxDrawdown;
    }

    if (component.type === 'DATA_HANDLING') {
      parameters.timeframe = params.timeframe;
      parameters.symbols = params.symbols;
      parameters.lookback = 100; // 默认值
    }

    return parameters;
  }

  /**
   * 获取组件代码模板
   */
  private getComponentCodeTemplate(type: ComponentType): ComponentCodeTemplate | null {
    // 支持按 type 或 id 查找
    const direct = this.codeTemplates.get(type as any);
    if (direct) return direct;

    for (const template of this.codeTemplates.values()) {
      if (template.type === type) return template;
    }

    return null;
  }

  /**
   * 验证模板
   */
  async validateTemplate(template: StrategyTemplate): Promise<TemplateValidationResult> {
    const errors: TemplateValidationError[] = [];
    const warnings: TemplateValidationWarning[] = [];
    const suggestions: string[] = [];

    // 检查必需字段
    if (!template.id) {
      errors.push({
        component: 'template',
        field: 'id',
        message: '模板ID不能为空',
        severity: 'error'
      });
    }

    if (!template.name) {
      errors.push({
        component: 'template',
        field: 'name',
        message: '模板名称不能为空',
        severity: 'error'
      });
    }

    if (!template.category) {
      errors.push({
        component: 'template',
        field: 'category',
        message: '模板类别不能为空',
        severity: 'error'
      });
    }

    // 检查组件配置
    if (!template.requiredComponents || template.requiredComponents.length === 0) {
      warnings.push({
        component: 'template',
        field: 'components',
        message: '模板没有配置必需组件',
        suggestion: '建议添加基础的入场、出场和风险控制组件'
      });
    }

    // 检查组件类型覆盖
    const componentTypes = template.requiredComponents.map(c => c.type);
    const requiredTypes: ComponentType[] = ['ENTRY', 'EXIT', 'RISK', 'DATA_HANDLING'];

    for (const requiredType of requiredTypes) {
      if (!componentTypes.includes(requiredType)) {
        warnings.push({
          component: 'template',
          field: 'components',
          message: `缺少${requiredType}组件`,
          suggestion: `建议添加${requiredType}组件以提高策略完整性`
        });
      }
    }

    // 检查参数配置
    if (!template.defaultParameters) {
      warnings.push({
        component: 'template',
        field: 'parameters',
        message: '模板没有配置默认参数',
        suggestion: '建议配置默认参数以提高生成质量'
      });
    }

    // 计算评分
    let score = 100;
    score -= errors.length * 20;
    score -= warnings.length * 10;

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions,
      score: Math.max(0, score)
    };
  }

  /**
   * 初始化默认组件
   */
  private initializeDefaultComponents(): void {
    const defaultComponents: StrategyComponent[] = [
      {
        type: 'ENTRY',
        name: '基础入场逻辑',
        codeTemplate: '',
        requiredParams: ['symbols', 'timeframe'],
        validation: {
          requiredParams: ['symbols', 'timeframe'],
          validationRules: [],
          dependencies: []
        },
        description: '基础的策略入场逻辑组件'
      },
      {
        type: 'EXIT',
        name: '基础出场逻辑',
        codeTemplate: '',
        requiredParams: [],
        validation: {
          requiredParams: [],
          validationRules: [],
          dependencies: []
        },
        description: '基础的策略出场逻辑组件'
      },
      {
        type: 'RISK',
        name: '基础风险控制',
        codeTemplate: '',
        requiredParams: ['stopLoss', 'takeProfit'],
        validation: {
          requiredParams: ['stopLoss', 'takeProfit'],
          validationRules: [],
          dependencies: []
        },
        description: '基础的风险控制组件'
      },
      {
        type: 'DATA_HANDLING',
        name: '基础数据处理',
        codeTemplate: '',
        requiredParams: ['timeframe', 'symbols'],
        validation: {
          requiredParams: ['timeframe', 'symbols'],
          validationRules: [],
          dependencies: []
        },
        description: '基础的数据处理组件'
      }
    ];

    defaultComponents.forEach(component => {
      this.components.set(component.type, component);
    });
  }

  /**
   * 初始化默认代码模板
   */
  private initializeDefaultCodeTemplates(): void {
    const defaultTemplates: ComponentCodeTemplate[] = [
      {
        id: 'default_entry',
        name: '默认入场逻辑',
        type: 'ENTRY',
        description: '基础的策略入场逻辑',
        codeTemplate: `# 入场逻辑组件
    def ${'$entry_name'}(\${context}, \${data}):
      """基于${'$indicator'}${'$condition'}的入场信号"""
      ${'$logic_code'}`,
        placeholders: [
          { name: 'entry_name', type: 'string', required: true, description: '函数名' },
          { name: 'indicator', type: 'string', required: true, description: '技术指标' },
          { name: 'condition', type: 'string', required: true, description: '入场条件' },
          { name: 'logic_code', type: 'string', required: true, description: '入场逻辑代码' }
        ],
        parameters: [
          { name: 'entry_name', type: 'string', required: true, description: '函数名' },
          { name: 'indicator', type: 'string', required: true, description: '技术指标' },
          { name: 'condition', type: 'string', required: true, description: '入场条件' },
          { name: 'logic_code', type: 'string', required: true, description: '入场逻辑代码' }
        ],
        imports: ['pandas as pd', 'numpy as np'],
        requiredParams: ['symbols', 'timeframe'],
        optionalParams: [],
        validation: {
          requiredParams: ['symbols', 'timeframe'],
          validationRules: [],
          dependencies: []
        }
      },
      {
        id: 'default_exit',
        name: '默认出场逻辑',
        type: 'EXIT',
        description: '基础的策略出场逻辑',
        codeTemplate: `# 出场逻辑组件
    def ${'$exit_name'}(\${context}, \${data}, \${position}):
      """基于${'$indicator'}${'$condition'}的出场信号"""
      ${'$logic_code'}`,
        placeholders: [
          { name: 'exit_name', type: 'string', required: true, description: '函数名' },
          { name: 'indicator', type: 'string', required: true, description: '技术指标' },
          { name: 'condition', type: 'string', required: true, description: '出场条件' },
          { name: 'logic_code', type: 'string', required: true, description: '出场逻辑代码' }
        ],
        parameters: [
          { name: 'exit_name', type: 'string', required: true, description: '函数名' },
          { name: 'indicator', type: 'string', required: true, description: '技术指标' },
          { name: 'condition', type: 'string', required: true, description: '出场条件' },
          { name: 'logic_code', type: 'string', required: true, description: '出场逻辑代码' }
        ],
        imports: [],
        requiredParams: [],
        optionalParams: ['position'],
        validation: {
          requiredParams: [],
          validationRules: [],
          dependencies: []
        }
      },
      {
        id: 'default_risk',
        name: '默认风险控制',
        type: 'RISK',
        description: '基础的风险控制组件',
        codeTemplate: `# 风险控制组件
    def ${'$risk_name'}(\${context}, \${data}, \${position}):
      """${'$description'}"""
      ${'$logic_code'}`,
        placeholders: [
          { name: 'risk_name', type: 'string', required: true, description: '函数名' },
          { name: 'description', type: 'string', required: true, description: '组件描述' },
          { name: 'logic_code', type: 'string', required: true, description: '风险控制逻辑' }
        ],
        parameters: [
          { name: 'risk_name', type: 'string', required: true, description: '函数名' },
          { name: 'description', type: 'string', required: true, description: '组件描述' },
          { name: 'logic_code', type: 'string', required: true, description: '风险控制逻辑' }
        ],
        imports: [],
        requiredParams: ['stopLoss', 'takeProfit'],
        optionalParams: ['maxDrawdown', 'positionSize'],
        validation: {
          requiredParams: ['stopLoss', 'takeProfit'],
          validationRules: [],
          dependencies: []
        }
      },
      {
        id: 'default_data',
        name: '默认数据处理',
        type: 'DATA_HANDLING',
        description: '基础的数据处理组件',
        codeTemplate: `# 数据处理组件
    def ${'$data_name'}(\${context}, \${symbol}, \${timeframe}):
      """${'$description'}"""
      ${'$logic_code'}`,
        placeholders: [
          { name: 'data_name', type: 'string', required: true, description: '函数名' },
          { name: 'symbol', type: 'string', required: true, description: '股票代码' },
          { name: 'timeframe', type: 'string', required: true, description: '时间框架' },
          { name: 'description', type: 'string', required: true, description: '组件描述' },
          { name: 'logic_code', type: 'string', required: true, description: '数据处理逻辑' }
        ],
        parameters: [
          { name: 'data_name', type: 'string', required: true, description: '数据名称' },
          { name: 'symbol', type: 'string', required: true, description: '股票代码' },
          { name: 'timeframe', type: 'string', required: true, description: '时间框架' },
          { name: 'description', type: 'string', required: true, description: '组件描述' },
          { name: 'logic_code', type: 'string', required: true, description: '数据处理逻辑' }
        ],
        imports: ['pandas as pd', 'numpy as np'],
        requiredParams: ['timeframe', 'symbols'],
        optionalParams: ['lookback'],
        validation: {
          requiredParams: ['timeframe', 'symbols'],
          validationRules: [],
          dependencies: []
        }
      }
    ];

    defaultTemplates.forEach(template => {
      this.codeTemplates.set(template.id, template);
      // 兼容按组件类型直接查找模板
      this.codeTemplates.set(template.type as any, template);
    });
  }

  /**
   * 获取参数映射
   */
  private getParameterMapping(_template: StrategyTemplate): Record<string, any> {
    // 基础参数映射
    return {
      // 策略参数映射
      'description': 'userParams.description',
      'market': 'userParams.market',
      'riskLevel': 'userParams.riskLevel',
      'timeframe': 'userParams.timeframe',
      'strategyLength': 'userParams.strategyLength',
      'backtestPeriod': 'userParams.backtestPeriod',

      // 资金参数映射
      'initialCapital': 'userParams.initialCapital',
      'positionSize': 'userParams.positionSize',
      'maxPositions': 'userParams.maxPositions',

      // 风险参数映射
      'stopLoss': 'userParams.stopLoss',
      'takeProfit': 'userParams.takeProfit',
      'maxDrawdown': 'userParams.maxDrawdown',

      // 股票池参数映射
      'symbols': 'userParams.symbols',
      'symbol': 'userParams.symbols[0]', // 第一只股票

      // 交易参数映射
      'commissionRate': 'userParams.commissionRate',
      'slippage': 'userParams.slippage',
      'benchmark': 'userParams.benchmark'
    };
  }

  /**
   * 获取所有模板
   */
  getTemplates(): StrategyTemplate[] {
    return Array.from(this.templates.values());
  }

  /**
   * 获取指定模板
   */
  getTemplate(id: string): StrategyTemplate | null {
    return this.templates.get(id) || null;
  }

  /**
   * 添加模板
   */
  addTemplate(template: StrategyTemplate): void {
    this.templates.set(template.id, template);
  }

  /**
   * 更新模板
   */
  updateTemplate(template: StrategyTemplate): void {
    if (this.templates.has(template.id)) {
      this.templates.set(template.id, { ...template, updatedAt: new Date() });
    }
  }

  /**
   * 删除模板
   */
  removeTemplate(id: string): boolean {
    return this.templates.delete(id);
  }

  /**
   * 获取模板使用统计
   */
  getTemplateStats(): Record<string, any> {
    // 这里可以实现模板使用统计
    return {};
  }
}

// 导出单例实例
export const templateEngine = new TemplateEngine();
