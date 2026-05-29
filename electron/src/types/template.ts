/**
 * 策略模板系统类型定义
 * 用于支持结构化的策略生成和模板匹配
 */

import {
  StrategyCategory,
  ComponentType,
  MarketType,
  Timeframe,
  RiskLevel,
  StrategyParams,
  StrategyComponent,
  ValidationRule,
  ComponentValidation,
  StrategyTemplate
} from './strategy';

// Re-export the imported types to make them available to other files
export type {
  StrategyCategory,
  ComponentType,
  MarketType,
  Timeframe,
  RiskLevel,
  StrategyParams,
  StrategyComponent,
  ValidationRule,
  ComponentValidation,
  StrategyTemplate
};


// 模板匹配结果
export interface TemplateMatch {
  template: StrategyTemplate;
  confidence: number;
  reason: string;
  adaptations: string[];
  score: number;
  matchFactors: {
    category: number;
    description: number;
    parameters: number;
    riskLevel: number;
  };
}

// 模板匹配配置
export interface TemplateMatchingConfig {
  weights: {
    category: number;
    description: number;
    parameters: number;
    riskLevel: number;
    market: number;
    timeframe: number;
  };
  thresholds: {
    minConfidence: number;
    maxResults: number;
  };
}

// 代码生成阶段
export interface GenerationStage {
  name: string;
  type: 'framework' | 'imports' | 'data_handling' | 'logic' | 'risk_control' | 'optimization';
  order: number;
  required: boolean;
  dependencies: string[];
}

// 组件代码模板
export interface ComponentCodeTemplate {
  id: string;
  name: string;
  type: ComponentType;
  description: string;
  codeTemplate: string;
  placeholders: TemplatePlaceholder[];
  parameters: TemplateParameter[];
  requiredParams: string[];
  optionalParams: string[];
  imports: string[];
  validation?: ComponentValidation;
}

// 模板占位符
export interface TemplatePlaceholder {
  name: string;
  description: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  defaultValue?: any;
  validation?: ValidationRule;
}

// 模板参数
export interface TemplateParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  defaultValue?: any;
  validation?: ValidationRule;
  mapping?: {
    [key: string]: any;
  };
}

// 策略生成请求
export interface StrategyGenerationRequest {
  userParams: StrategyParams;
  template?: StrategyTemplate;
  customComponents?: StrategyComponent[];
  generationConfig: {
    includeComments: boolean;
    includeLogging: boolean;
    includeErrorHandling: boolean;
    includePerformanceOptimization: boolean;
  };
}

// 策略生成结果
export interface StrategyGenerationResult {
  success: boolean;
  template?: StrategyTemplate;
  strategy?: {
    code: string;
    parameters: StrategyParams;
    components: GeneratedComponent[];
    metadata: {
      generationTime: number;
      templateId: string;
      customizations: string[];
    };
  };
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

// 生成的组件
export interface GeneratedComponent {
  type: ComponentType;
  name: string;
  code: string;
  parameters: Record<string, any>;
  validation: {
    isValid: boolean;
    errors: string[];
    warnings: string[];
  };
}

// 模板库配置
export interface TemplateLibrary {
  templates: StrategyTemplate[];
  categories: StrategyCategory[];
  components: StrategyComponent[];
  version: string;
  lastUpdated: Date;
}

// 模板使用统计
export interface TemplateUsageStats {
  templateId: string;
  usageCount: number;
  successRate: number;
  avgGenerationTime: number;
  userRatings: number[];
  lastUsed: Date;
}

// 模板评分系统
export interface TemplateScoring {
  completeness: number;
  accuracy: number;
  efficiency: number;
  popularity: number;
  overall: number;
}

// 模板验证结果
export interface TemplateValidationResult {
  isValid: boolean;
  errors: TemplateValidationError[];
  warnings: TemplateValidationWarning[];
  suggestions: string[];
  score: number;
}

// 模板验证错误
export interface TemplateValidationError {
  component: string;
  field: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

// 模板验证警告
export interface TemplateValidationWarning {
  component: string;
  field: string;
  message: string;
  suggestion?: string;
}

// 模板更新请求
export interface TemplateUpdateRequest {
  templateId: string;
  updates: Partial<StrategyTemplate>;
  reason: string;
}

// 模板导入/导出
export interface TemplateExport {
  templates: StrategyTemplate[];
  format: 'json' | 'yaml' | 'csv';
  metadata: {
    exportedBy: string;
    exportedAt: Date;
    version: string;
  };
}

// 模板导入结果
export interface TemplateImportResult {
  success: boolean;
  imported: number;
  skipped: number;
  errors: string[];
  warnings: string[];
}

// 模板搜索过滤器
export interface TemplateSearchFilter {
  category?: StrategyCategory;
  riskLevel?: RiskLevel;
  market?: MarketType;
  timeframe?: Timeframe;
  tags?: string[];
  minCapital?: number;
  maxSymbols?: number;
  complexity?: 'low' | 'medium' | 'high';
}

// 模板排序选项
export type TemplateSortOption =
  | 'name'
  | 'createdAt'
  | 'popularity'
  | 'rating'
  | 'complexity'
  | 'successRate';

// 模板分页结果
export interface TemplateSearchResult {
  templates: StrategyTemplate[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  filters: TemplateSearchFilter;
  sort: TemplateSortOption;
  searchTime: number;
}
