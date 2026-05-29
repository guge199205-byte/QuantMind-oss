/**
 * 集成验证系统
 * 整合模板验证、参数验证和实时代码验证功能
 */

import {
  StrategyTemplate,
  TemplateValidationError,
  TemplateValidationWarning
} from '../types/template';
import {
  StrategyParams,
  RealTimeValidationRequest,
  ValidationContext
} from '../types/strategy';
import { parameterValidator } from '../utils/parameterValidator';
import { codeProcessor } from './codeProcessor';
import { templateMatcher } from './templateMatcher';

// ==================== 验证类型定义 ====================

export interface IntegratedValidationRequest {
  // 基础信息
  userParams: StrategyParams;
  userDescription?: string;
  selectedTemplate?: StrategyTemplate;

  // 代码相关
  code?: string;
  stage?: 'parameter_input' | 'template_selection' | 'code_generation' | 'code_editing';

  // 验证配置
  validationConfig?: {
    checkParameters: boolean;
    checkTemplate: boolean;
    checkCode: boolean;
    checkCompatibility: boolean;
    strictMode: boolean;
  };
}

export interface IntegratedValidationResult {
  success: boolean;
  stage: string;
  confidence: number;

  // 参数验证结果
  parameterValidation: {
    isValid: boolean;
    errors: Array<{
      field: string;
      message: string;
      severity: 'error' | 'warning';
    }>;
    suggestions: string[];
    adjustedParams?: StrategyParams;
  };

  // 模板验证结果
  templateValidation: {
    isValid: boolean;
    template?: StrategyTemplate;
    matchConfidence?: number;
    errors: TemplateValidationError[];
    warnings: TemplateValidationWarning[];
    suggestions: string[];
  };

  // 代码验证结果
  codeValidation: {
    isValid: boolean;
    syntaxErrors: Array<{
      line: number;
      message: string;
      severity: 'error' | 'warning';
    }>;
    logicErrors: Array<{
      line: number;
      message: string;
      severity: 'error' | 'warning';
    }>;
    qualityScore: number;
    suggestions: string[];
  };

  // 兼容性验证
  compatibilityValidation: {
    isValid: boolean;
    issues: string[];
    recommendations: string[];
  };

  // 综合评估
  overallScore: number;
  readyForGeneration: boolean;
  nextSteps: string[];
}

export interface ValidationPipeline {
  stages: Array<{
    name: string;
    validator: (request: IntegratedValidationRequest) => Promise<any>;
    required: boolean;
    dependencies: string[];
  }>;
}

// ==================== 主验证器类 ====================

export class IntegratedValidator {
  private pipeline: ValidationPipeline;

  constructor() {
    this.pipeline = this.buildValidationPipeline();
  }

  /**
   * 执行集成验证
   */
  async validate(request: IntegratedValidationRequest): Promise<IntegratedValidationResult> {
    const config = request.validationConfig || {
      checkParameters: true,
      checkTemplate: true,
      checkCode: true,
      checkCompatibility: true,
      strictMode: false
    };

    const stage = request.stage || 'parameter_input';
    const startTime = Date.now();

    try {
      // 1. 参数验证
      const parameterValidation = await this.validateParameters(request);

      // 2. 模板验证
      const templateValidation = await this.validateTemplate(request);

      // 3. 代码验证
      const codeValidation = await this.validateCode(request);

      // 4. 兼容性验证
      const compatibilityValidation = await this.validateCompatibility(request, config);

      // 5. 综合评估
      const overallScore = this.calculateOverallScore(
        parameterValidation,
        templateValidation,
        codeValidation,
        compatibilityValidation
      );

      const readyForGeneration = this.checkReadinessForGeneration(
        parameterValidation,
        templateValidation,
        codeValidation,
        compatibilityValidation,
        config.strictMode
      );

      const nextSteps = this.generateNextSteps(
        stage,
        parameterValidation,
        templateValidation,
        codeValidation,
        compatibilityValidation
      );

      return {
        success: overallScore >= (config.strictMode ? 0.9 : 0.7),
        stage,
        confidence: overallScore,
        parameterValidation,
        templateValidation,
        codeValidation,
        compatibilityValidation,
        overallScore,
        readyForGeneration,
        nextSteps
      };

    } catch (error) {
      console.error('集成验证失败:', error);
      return {
        success: false,
        stage,
        confidence: 0,
        parameterValidation: {
          isValid: false,
          errors: [{ field: 'system', message: '验证系统错误', severity: 'error' }],
          suggestions: ['请稍后重试']
        },
        templateValidation: {
          isValid: false,
          errors: [{ component: 'system', field: 'validation', message: '模板验证失败', severity: 'error' }],
          warnings: [],
          suggestions: []
        },
        codeValidation: {
          isValid: false,
          syntaxErrors: [{ line: 0, message: '代码验证失败', severity: 'error' }],
          logicErrors: [],
          qualityScore: 0,
          suggestions: []
        },
        compatibilityValidation: {
          isValid: false,
          issues: ['系统验证失败'],
          recommendations: ['请检查输入参数']
        },
        overallScore: 0,
        readyForGeneration: false,
        nextSteps: ['检查系统状态']
      };
    }
  }

  /**
   * 验证参数
   */
  private async validateParameters(
    request: IntegratedValidationRequest
  ): Promise<IntegratedValidationResult['parameterValidation']> {
    const config = request.validationConfig || {
      checkParameters: true,
      checkTemplate: true,
      checkCode: true,
      checkCompatibility: true,
      strictMode: false
    };

    if (!config.checkParameters) {
      return {
        isValid: true,
        errors: [],
        suggestions: []
      };
    }

    try {
      const validation = parameterValidator.validate(request.userParams, parameterValidator.rules);

      // 转换错误格式
      const errors = validation.errors.map(error => ({
        field: 'general',
        message: error,
        severity: 'error' as 'error' | 'warning'
      }));

      return {
        isValid: validation.isValid,
        errors,
        suggestions: validation.suggestions
      };

    } catch (error) {
      return {
        isValid: false,
        errors: [{ field: 'validation', message: '参数验证失败', severity: 'error' }],
        suggestions: ['请检查输入参数']
      };
    }
  }

  /**
   * 验证模板
   */
  private async validateTemplate(
    request: IntegratedValidationRequest
  ): Promise<IntegratedValidationResult['templateValidation']> {
    const config = request.validationConfig || {
      checkParameters: true,
      checkTemplate: true,
      checkCode: true,
      checkCompatibility: true,
      strictMode: false
    };

    if (!config.checkTemplate) {
      return {
        isValid: true,
        errors: [],
        warnings: [],
        suggestions: []
      };
    }

    try {
      if (request.selectedTemplate) {
        // 验证选中的模板
        return this.validateSelectedTemplate(request, config);
      } else {
        // 查找合适的模板：先执行参数验证以传入后续模板验证
        const parameterValidation = await this.validateParameters(request);
        return this.findAndValidateTemplate(request, config, parameterValidation);
      }

    } catch (error) {
      return {
        isValid: false,
        errors: [{ component: 'template', field: 'validation', message: '模板验证失败', severity: 'error' }],
        warnings: [],
        suggestions: ['请选择合适的策略模板']
      };
    }
  }

  /**
   * 验证选中的模板
   */
  private async validateSelectedTemplate(
    request: IntegratedValidationRequest,
    _config: any
  ): Promise<IntegratedValidationResult['templateValidation']> {
    const template = request.selectedTemplate!;
    const errors: TemplateValidationError[] = [];
    const warnings: TemplateValidationWarning[] = [];
    const suggestions: string[] = [];

    // 1. 验证模板与参数的兼容性
    const compatibilityIssues = this.checkTemplateParameterCompatibility(template, request.userParams);
    errors.push(...compatibilityIssues.filter(issue => issue.severity === 'error'));
    warnings.push(...compatibilityIssues.filter(issue => issue.severity === 'warning'));

    // 2. 验证模板完整性
    const completenessIssues = this.checkTemplateCompleteness(template);
    if (completenessIssues.length > 0) {
      warnings.push(...completenessIssues);
    }

    // 3. 生成建议
    if (warnings.length > 0) {
      suggestions.push('建议调整参数以提高模板匹配度');
    }

    return {
      isValid: errors.length === 0,
      template,
      matchConfidence: this.calculateTemplateConfidence(template, request.userParams),
      errors,
      warnings,
      suggestions
    };
  }

  /**
   * 查找并验证模板
   */
  private async findAndValidateTemplate(
    request: IntegratedValidationRequest,
    _config: any,
    _parameterValidation: any
  ): Promise<IntegratedValidationResult['templateValidation']> {
    try {
      // 使用模板匹配器查找合适的模板
      const matches = await templateMatcher.matchTemplates(request.userParams, request.userDescription);

      if (matches.length === 0) {
        return {
          isValid: false,
          errors: [{
            component: 'template',
            field: 'matching',
            message: '未找到匹配的策略模板',
            severity: 'error'
          }],
          warnings: [],
          suggestions: ['请调整策略描述或参数']
        };
      }

      const bestMatch = matches[0];
      const warnings: TemplateValidationWarning[] = [];
      const suggestions: string[] = [];

      if (bestMatch.confidence < 0.7) {
        warnings.push({
          component: 'template',
          field: 'confidence',
          message: `模板匹配度较低 (${(bestMatch.confidence * 100).toFixed(1)}%)`,
          suggestion: '建议调整参数或选择其他模板'
        });
      }

      suggestions.push(...bestMatch.adaptations);

      return {
        isValid: true,
        template: bestMatch.template,
        matchConfidence: bestMatch.confidence,
        errors: [],
        warnings,
        suggestions
      };

    } catch (error) {
      return {
        isValid: false,
        errors: [{
          component: 'template',
          field: 'matching',
          message: '模板匹配失败',
          severity: 'error'
        }],
        warnings: [],
        suggestions: ['请稍后重试或手动选择模板']
      };
    }
  }

  /**
   * 验证代码
   */
  private async validateCode(
    request: IntegratedValidationRequest
  ): Promise<IntegratedValidationResult['codeValidation']> {
    const config = request.validationConfig || {
      checkParameters: true,
      checkTemplate: true,
      checkCode: true,
      checkCompatibility: true,
      strictMode: false
    };

    if (!config.checkCode || !request.code) {
      return {
        isValid: true,
        syntaxErrors: [],
        logicErrors: [],
        qualityScore: 100,
        suggestions: []
      };
    }

    try {
      const context: ValidationContext = {
        userParams: request.userParams,
        market: request.userParams.market || 'CN',
        timeframe: request.userParams.timeframe || '1d'
      };

      const validationRequest: RealTimeValidationRequest = {
        code: request.code,
        context,
        stage: request.stage || 'code_generation'
      };

      const result = await codeProcessor.realTimeValidator.validate(request.code, []);

      const syntaxErrors = result.errors.map((error) => ({
        line: 0,
        message: error,
        severity: 'error' as const
      }));

      const logicErrors = result.warnings.map((warning) => ({
        line: 0,
        message: warning,
        severity: 'warning' as const
      }));

      // 分析代码质量
      const qualityScore = this.calculateCodeQuality(request.code, result);

      return {
        isValid: result.isValid,
        syntaxErrors,
        logicErrors,
        qualityScore,
        suggestions: []
      };

    } catch (error) {
      return {
        isValid: false,
        syntaxErrors: [{ line: 0, message: '代码验证失败', severity: 'error' }],
        logicErrors: [],
        qualityScore: 0,
        suggestions: ['请检查代码语法']
      };
    }
  }

  /**
   * 验证兼容性
   */
  private async validateCompatibility(
    request: IntegratedValidationRequest,
    config: any
  ): Promise<IntegratedValidationResult['compatibilityValidation']> {
    if (!config.checkCompatibility) {
      return {
        isValid: true,
        issues: [],
        recommendations: []
      };
    }

    const issues: string[] = [];
    const recommendations: string[] = [];

    // 1. 参数与市场兼容性
    const marketCompatibility = this.checkMarketCompatibility(request.userParams);
    issues.push(...marketCompatibility.issues);
    recommendations.push(...marketCompatibility.recommendations);

    // 2. 时间框架兼容性
    const timeframeCompatibility = this.checkTimeframeCompatibility(request.userParams);
    issues.push(...timeframeCompatibility.issues);
    recommendations.push(...timeframeCompatibility.recommendations);

    // 3. 风险等级兼容性
    const riskCompatibility = this.checkRiskCompatibility(request.userParams);
    issues.push(...riskCompatibility.issues);
    recommendations.push(...riskCompatibility.recommendations);

    // 4. 资金兼容性
    const capitalCompatibility = this.checkCapitalCompatibility(request.userParams);
    issues.push(...capitalCompatibility.issues);
    recommendations.push(...capitalCompatibility.recommendations);

    return {
      isValid: issues.length === 0,
      issues,
      recommendations
    };
  }

  /**
   * 计算综合得分
   */
  private calculateOverallScore(
    parameterValidation: any,
    templateValidation: any,
    codeValidation: any,
    compatibilityValidation: any
  ): number {
    const weights = {
      parameters: 0.25,
      template: 0.25,
      code: 0.30,
      compatibility: 0.20
    };

    let score = 0;

    // 参数得分
    const parameterScore = parameterValidation.isValid ? 1.0 : 0.5;
    score += parameterScore * weights.parameters;

    // 模板得分
    let templateScore = 0;
    if (templateValidation.isValid) {
      templateScore = templateValidation.matchConfidence ? templateValidation.matchConfidence : 0.8;
    } else {
      templateScore = 0.3;
    }
    score += templateScore * weights.template;

    // 代码得分
    const codeScore = codeValidation.qualityScore / 100;
    score += codeScore * weights.code;

    // 兼容性得分
    const compatibilityScore = compatibilityValidation.isValid ? 1.0 : 0.6;
    score += compatibilityScore * weights.compatibility;

    return Math.round(score * 100) / 100;
  }

  /**
   * 检查是否准备好生成代码
   */
  private checkReadinessForGeneration(
    parameterValidation: any,
    templateValidation: any,
    codeValidation: any,
    compatibilityValidation: any,
    strictMode: boolean
  ): boolean {
    const minParameterScore = strictMode ? 1.0 : 0.8;
    const minTemplateScore = strictMode ? 0.8 : 0.6;
    const minCompatibilityScore = strictMode ? 1.0 : 0.8;

    return (
      (parameterValidation.isValid || parameterValidation.adjustedParams) &&
      templateValidation.isValid &&
      templateValidation.matchConfidence! >= minTemplateScore &&
      compatibilityValidation.isValid &&
      (!strictMode || codeValidation.isValid)
    );
  }

  /**
   * 生成下一步建议
   */
  private generateNextSteps(
    stage: string,
    parameterValidation: any,
    templateValidation: any,
    codeValidation: any,
    compatibilityValidation: any
  ): string[] {
    const nextSteps: string[] = [];

    if (!parameterValidation.isValid) {
      nextSteps.push('修正参数验证错误');
    }

    if (!templateValidation.isValid) {
      nextSteps.push('选择合适的策略模板');
    }

    if (templateValidation.matchConfidence && templateValidation.matchConfidence < 0.7) {
      nextSteps.push('调整参数以提高模板匹配度');
    }

    if (!compatibilityValidation.isValid) {
      nextSteps.push('解决兼容性问题');
    }

    if (codeValidation.syntaxErrors.length > 0) {
      nextSteps.push('修复代码语法错误');
    }

    if (codeValidation.logicErrors.length > 0) {
      nextSteps.push('优化代码逻辑');
    }

    if (nextSteps.length === 0) {
      nextSteps.push('可以开始生成策略代码');
    }

    return nextSteps;
  }

  // ==================== 辅助方法 ====================

  /**
   * 构建验证流水线
   */
  private buildValidationPipeline(): ValidationPipeline {
    return {
      stages: [
        {
          name: 'parameter_validation',
          validator: this.validateParameters.bind(this),
          required: true,
          dependencies: []
        },
        {
          name: 'template_validation',
          validator: this.validateTemplate.bind(this),
          required: true,
          dependencies: ['parameter_validation']
        },
        {
          name: 'code_validation',
          validator: this.validateCode.bind(this),
          required: false,
          dependencies: ['template_validation']
        },
        {
          name: 'compatibility_validation',
          validator: (req: IntegratedValidationRequest) => this.validateCompatibility(req, {
            checkParameters: true,
            checkTemplate: true,
            checkCode: true,
            checkCompatibility: true,
            strictMode: false
          }),
          required: true,
          dependencies: ['parameter_validation', 'template_validation']
        }
      ]
    };
  }

  /**
   * 检查模板参数兼容性
   */
  private checkTemplateParameterCompatibility(
    template: StrategyTemplate,
    params: StrategyParams
  ): TemplateValidationError[] {
    const errors: TemplateValidationError[] = [];

    // 检查必需参数
    if (template.defaultParameters) {
      for (const [key, value] of Object.entries(template.defaultParameters)) {
        const paramValue = params[key as keyof StrategyParams];
        if (paramValue === undefined || paramValue === null) {
          errors.push({
            component: 'template',
            field: key,
            message: `缺少必需参数: ${key}`,
            severity: 'error'
          });
        }
      }
    }

    // 检查数值范围
    if (params.initialCapital && params.initialCapital < template.minCapital) {
      errors.push({
        component: 'template',
        field: 'initialCapital',
        message: `初始资金低于模板最低要求 (${template.minCapital}元)`,
        severity: 'warning'
      });
    }

    return errors;
  }

  /**
   * 检查模板完整性
   */
  private checkTemplateCompleteness(template: StrategyTemplate): TemplateValidationWarning[] {
    const warnings: TemplateValidationWarning[] = [];

    if (!template.description || template.description.length < 20) {
      warnings.push({
        component: 'template',
        field: 'description',
        message: '模板描述过于简短',
        suggestion: '建议提供更详细的策略说明'
      });
    }

    if (!template.tags || template.tags.length === 0) {
      warnings.push({
        component: 'template',
        field: 'tags',
        message: '缺少模板标签',
        suggestion: '添加相关标签有助于模板匹配'
      });
    }

    return warnings;
  }

  /**
   * 计算模板置信度
   */
  private calculateTemplateConfidence(template: StrategyTemplate, params: StrategyParams): number {
    let confidence = 0.5; // 基础置信度

    // 风险等级匹配
    if (params.riskLevel && template.suitableRiskLevels.includes(params.riskLevel as any)) {
      confidence += 0.2;
    }

    // 市场匹配
    if (params.market && template.suitableMarkets.includes(params.market as any)) {
      confidence += 0.15;
    }

    // 时间框架匹配
    if (params.timeframe && template.suitableTimeframes.includes(params.timeframe as any)) {
      confidence += 0.15;
    }

    return Math.min(1.0, confidence);
  }

  /**
   * 计算代码质量
   */
  private calculateCodeQuality(code: string, validationResult: any): number {
    let score = 100;

    // 语法错误扣分
    score -= validationResult.errors.length * 20;

    // 逻辑错误扣分
    score -= validationResult.warnings.length * 10;

    // 代码长度影响
    const lines = code.split('\n').length;
    if (lines < 50) score -= 10; // 代码太短
    if (lines > 1000) score -= 10; // 代码太长

    // 代码复杂度影响（简单估计）
    const complexity = (code.match(/if|for|while|def/g) || []).length;
    if (complexity > 20) score -= 15;

    return Math.max(0, score);
  }

  /**
   * 检查市场兼容性
   */
  private checkMarketCompatibility(params: StrategyParams): { issues: string[]; recommendations: string[] } {
    const issues: string[] = [];
    const recommendations: string[] = [];

    if (!params.market) {
      issues.push('未指定交易市场');
      recommendations.push('请指定交易市场（如：CN, US, HK）');
    }

    return { issues, recommendations };
  }

  /**
   * 检查时间框架兼容性
   */
  private checkTimeframeCompatibility(params: StrategyParams): { issues: string[]; recommendations: string[] } {
    const issues: string[] = [];
    const recommendations: string[] = [];

    if (!params.timeframe) {
      issues.push('未指定时间框架');
      recommendations.push('请指定时间框架（如：1m, 5m, 1h, 1d）');
    }

    return { issues, recommendations };
  }

  /**
   * 检查风险兼容性
   */
  private checkRiskCompatibility(params: StrategyParams): { issues: string[]; recommendations: string[] } {
    const issues: string[] = [];
    const recommendations: string[] = [];

    if (!params.riskLevel) {
      issues.push('未指定风险等级');
      recommendations.push('请指定风险等级（low, medium, high）');
    }

    return { issues, recommendations };
  }

  /**
   * 检查资金兼容性
   */
  private checkCapitalCompatibility(params: StrategyParams): { issues: string[]; recommendations: string[] } {
    const issues: string[] = [];
    const recommendations: string[] = [];

    if (!params.initialCapital) {
      issues.push('未指定初始资金');
      recommendations.push('请指定初始资金数额');
    } else if (params.initialCapital < 10000) {
      issues.push('初始资金过少，可能无法正常交易');
      recommendations.push('建议初始资金不少于10,000元');
    }

    return { issues, recommendations };
  }
}

// ==================== 导出 ====================

export const integratedValidator = new IntegratedValidator();
