/**
 * 增强版状态管理
 * 集成参数验证、代码处理和实时验证功能
 */

import { atom, selector } from 'recoil';
import {
  StrategyParams as IStrategyParams,
  ValidationResult as IValidationResult,
  Strategy as IStrategy,
  ChatMessage as IChatMessage,
  BacktestResult as IBacktestResult,
  CodeAnalysis,
  RealTimeValidationResponse,
  GenerationResult
} from '../types/strategy';
import {
  strategyParamsState,
  currentStrategyState,
  ValidationResult,
  Strategy,
  ChatMessage,
  BacktestResult
} from './atoms';

// 基础状态保持不变，导出原有的atoms
export {
  currentTabState,
  strategyParamsState,
  chatMessagesState,
  currentStrategyState,
  backtestResultState,
  isGeneratingState,
  strategyHistoryState,
  activeSectionState
} from './atoms';

// 新增：参数验证状态
export const paramValidationState = atom<ValidationResult | null>({
  key: 'paramValidationState',
  default: null
});

// 新增：调整后的参数状态
export const adjustedParamsState = atom<IStrategyParams | null>({
  key: 'adjustedParamsState',
  default: null
});

// 新增：实时代码验证状态
export const codeValidationState = atom<RealTimeValidationResponse | null>({
  key: 'codeValidationState',
  default: null
});

// 新增：代码分析状态
export const codeAnalysisState = atom<CodeAnalysis | null>({
  key: 'codeAnalysisState',
  default: null
});

// 新增：生成状态详情
export const generationState = atom<{
  status: 'idle' | 'validating' | 'generating' | 'completed' | 'error';
  message: string;
  progress?: number;
  stage?: string;
}>({
  key: 'generationState',
  default: {
    status: 'idle',
    message: ''
  }
});

// 新增：验证错误状态
export const validationErrorsState = atom<Array<{
  field: string;
  message: string;
  type: 'error' | 'warning';
}>>({
  key: 'validationErrorsState',
  default: []
});

// 新增：优化建议状态
export const optimizationSuggestionsState = atom<string[]>({
  key: 'optimizationSuggestionsState',
  default: []
});

// 新增：UI状态
export const uiState = atom<{
  showValidationModal: boolean;
  showLoadingModal: boolean;
  showAdvancedParams: boolean;
  showCodeValidation: boolean;
  activeErrorTab: 'errors' | 'warnings' | 'suggestions';
}>({
  key: 'uiState',
  default: {
    showValidationModal: false,
    showLoadingModal: false,
    showAdvancedParams: false,
    showCodeValidation: true,
    activeErrorTab: 'errors'
  }
});

// 新增：生成历史状态（详细版）
export const detailedGenerationHistoryState = atom<GenerationResult[]>({
  key: 'detailedGenerationHistoryState',
  default: []
});

// 新增：实时验证配置状态
export const validationConfigState = atom<{
  enabled: boolean;
  debounceMs: number;
  autoFormat: boolean;
  showLineNumbers: boolean;
  enableSyntaxHighlight: boolean;
}>({
  key: 'validationConfigState',
  default: {
    enabled: true,
    debounceMs: 1000,
    autoFormat: true,
    showLineNumbers: true,
    enableSyntaxHighlight: true
  }
});

// 选择器：计算策略状态摘要
export const strategySummaryState = selector({
  key: 'strategySummaryState',
  get: ({ get }) => {
    const strategy = get(currentStrategyState);
    const validation = get(codeValidationState);
    const analysis = get(codeAnalysisState);

    if (!strategy) {
      return {
        hasStrategy: false,
        isValid: false,
        complexity: 0,
        hasErrors: false,
        hasWarnings: false
      };
    }

    return {
      hasStrategy: true,
      isValid: validation?.isValid ?? false,
      complexity: analysis?.complexity ?? 0,
      hasErrors: (validation?.errors?.length || 0) > 0,
      hasWarnings: (validation?.warnings?.length || 0) > 0,
      errorCount: validation?.errors?.length || 0,
      warningCount: validation?.warnings?.length || 0,
      version: strategy.metadata.version,
      lastUpdated: strategy.metadata.updatedAt
    };
  }
});

// 选择器：计算参数完整性
export const paramsCompletenessState = selector({
  key: 'paramsCompletenessState',
  get: ({ get }) => {
    const params = get(strategyParamsState);
    const validation = get(paramValidationState);

    if (!params) {
      return {
        completeness: 0,
        requiredFields: [],
        optionalFields: [],
        isValid: false
      };
    }

    const requiredFields = ['description', 'market', 'timeframe', 'riskLevel', 'initialCapital'];
    const optionalFields = ['style', 'strategyLength', 'backtestPeriod', 'maxDrawdown', 'commissionRate', 'slippage'];

    const completedRequired = requiredFields.filter(field => {
      const value = params[field as keyof IStrategyParams];
      return value !== undefined && value !== '' && value !== 0;
    });

    const completedOptional = optionalFields.filter(field => {
      const value = params[field as keyof IStrategyParams];
      return value !== undefined && value !== '' && value !== 0;
    });

    const completeness = Math.round(((completedRequired.length + completedOptional.length) / (requiredFields.length + optionalFields.length)) * 100);

    return {
      completeness,
      requiredFields: completedRequired,
      optionalFields: completedOptional,
      isValid: validation?.isValid ?? false
    };
  }
});

// 选择器：计算代码质量评分
export const codeQualityState = selector({
  key: 'codeQualityState',
  get: ({ get }) => {
    const analysis = get(codeAnalysisState);
    const validation = get(codeValidationState);

    if (!analysis) {
      return {
        score: 0,
        grade: 'F',
        issues: [],
        strengths: []
      };
    }

    let score = 100;

    // 根据复杂度扣分
    if (analysis.complexity > 50) score -= 20;
    else if (analysis.complexity > 30) score -= 10;
    else if (analysis.complexity > 20) score -= 5;

    // 根据可维护性扣分
    score = Math.min(score, analysis.maintainability);

    // 根据错误扣分
    if (validation?.errors?.length && validation.errors.length > 0) {
      score -= validation.errors.length * 10;
    }

    // 根据警告扣分
    if (validation?.warnings?.length && validation.warnings.length > 0) {
      score -= validation.warnings.length * 5;
    }

    const grade = score >= 90 ? 'A' :
                score >= 80 ? 'B' :
                score >= 70 ? 'C' :
                score >= 60 ? 'D' : 'F';

    const issues = [
      ...analysis.missingRiskControls,
      ...analysis.performanceIssues,
      ...analysis.dataValidationGaps,
      ...analysis.errorHandling
    ];

    const strengths = [];
    if (analysis.missingRiskControls.length === 0) {
      strengths.push('完善的风险控制');
    }
    if (analysis.errorHandling.length === 0) {
      strengths.push('良好的错误处理');
    }
    if (analysis.complexity < 20) {
      strengths.push('代码简洁清晰');
    }
    if (analysis.maintainability > 80) {
      strengths.push('良好的可维护性');
    }

    return {
      score: Math.max(0, score),
      grade,
      issues,
      strengths
    };
  }
});

// 选择器：计算系统整体状态
export const systemHealthState = selector({
  key: 'systemHealthState',
  get: ({ get }) => {
    const validation = get(paramValidationState);
    const codeValidation = get(codeValidationState);
    const generation = get(generationState);
    const paramsCompleteness = get(paramsCompletenessState);
    const codeQuality = get(codeQualityState);

    const issues = [];

    // 参数相关
    if (validation && !validation.isValid) {
      issues.push(`参数验证失败 (${validation.errors?.length || 0} 个错误)`);
    }

    // 代码相关
    if (codeValidation && !codeValidation.isValid) {
      issues.push(`代码验证失败 (${codeValidation.errors?.length || 0} 个错误)`);
    }

    // 生成相关
    if (generation.status === 'error') {
      issues.push('生成过程出错');
    }

    // 完整性相关
    if (paramsCompleteness.completeness < 50) {
      issues.push('参数信息不完整');
    }

    // 质量相关
    if (codeQuality.grade === 'F') {
      issues.push('代码质量较差');
    }

    const healthScore = Math.max(0, 100 - issues.length * 20);

    return {
      score: healthScore,
      status: healthScore >= 80 ? 'healthy' :
               healthScore >= 60 ? 'warning' : 'error',
      issues,
      totalIssues: issues.length
    };
  }
});

// 新增：策略模板相关状态
export const selectedTemplateState = atom<string | null>({
  key: 'selectedTemplateState',
  default: null
});

export const availableTemplatesState = atom<Array<{
  id: string;
  name: string;
  category: string;
  description: string;
  tags: string[];
}>>({
  key: 'availableTemplatesState',
  default: []
});

// 新增：多轮对话优化状态
export const conversationOptimizerState = atom<{
  enabled: boolean;
  mode: 'manual' | 'auto';
  suggestions: Array<{
    type: string;
    priority: string;
    description: string;
  }>;
}>({
  key: 'conversationOptimizerState',
  default: {
    enabled: true,
    mode: 'manual',
    suggestions: []
  }
});

// 新增：实时验证缓存状态
export const validationCacheState = atom<Map<string, RealTimeValidationResponse>>({
  key: 'validationCacheState',
  default: new Map()
});

// 新增：用户偏好设置
export const userPreferencesState = atom<{
  autoSave: boolean;
  autoFormat: boolean;
  showValidation: boolean;
  theme: 'light' | 'dark' | 'auto';
  language: 'zh' | 'en';
  notifications: boolean;
}>({
  key: 'userPreferencesState',
  default: {
    autoSave: true,
    autoFormat: true,
    showValidation: true,
    theme: 'auto',
    language: 'zh',
    notifications: true
  }
});

// 新增：性能监控状态
export const performanceState = atom<{
  generationTime: number;
  validationTime: number;
  codeComplexity: number;
  memoryUsage: number;
}>({
  key: 'performanceState',
  default: {
    generationTime: 0,
    validationTime: 0,
    codeComplexity: 0,
    memoryUsage: 0
  }
});

// 导出所有状态和选择器
export * from './atoms';
