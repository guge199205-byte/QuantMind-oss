import { atom } from 'recoil';
import { StrategyParams as IStrategyParams, ChatMessage as IChatMessage, Strategy as IStrategy } from '../types/strategy';

export type DashboardTab = 'dashboard' | 'strategy' | 'backtest' | 'trading' | 'notifications' | 'community' | 'profile' | 'admin';

export const currentTabState = atom<DashboardTab>({
  key: 'currentTabState',
  default: 'dashboard'
});

// AI策略相关状态 - 使用统一的类型定义
export type StrategyParams = IStrategyParams;

export type ChatMessage = IChatMessage;

export type Strategy = IStrategy;

export interface BacktestResult {
  id: string;
  strategyId: string;
  performance: {
    totalReturn: number;
    annualizedReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    profitFactor: number;
  };
  trades: any[];
  equity: any[];
  charts: {
    equity: string;
    drawdown: string;
    returns: string;
  };
}

// 策略参数状态
export const strategyParamsState = atom<StrategyParams>({
  key: 'strategyParamsState',
  default: {
    description: '',
    market: 'CN',
    riskLevel: 'medium',
    style: 'custom',
    symbols: [],
    framework: 'miniqmt',
    outputFormat: 'miniqmt',
    timeframe: '1d',
    strategyLength: 'unlimited',
    backtestPeriod: '1year',
    initialCapital: 100000,
    positionSize: 10,
    maxPositions: 5,
    stopLoss: 5,
    takeProfit: 20,
    maxDrawdown: undefined,
    commissionRate: undefined,
    slippage: undefined,
    benchmark: undefined
  }
});

// 对话消息状态
export const chatMessagesState = atom<ChatMessage[]>({
  key: 'chatMessagesState',
  default: []
});

// 当前策略状态
export const currentStrategyState = atom<Strategy | null>({
  key: 'currentStrategyState',
  default: null
});

// 回测结果状态
export const backtestResultState = atom<BacktestResult | null>({
  key: 'backtestResultState',
  default: null
});

// AI生成状态
export const isGeneratingState = atom<boolean>({
  key: 'isGeneratingState',
  default: false
});

// 策略历史状态
export const strategyHistoryState = atom<Strategy[]>({
  key: 'strategyHistoryState',
  default: []
});

// 活动区域状态
export const activeSectionState = atom<'chat' | 'code' | 'backtest'>({
  key: 'activeSectionState',
  default: 'chat'
});

// ==================== 模板相关状态 ====================

export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  riskLevel: 'low' | 'medium' | 'high';
  complexity: 'low' | 'medium' | 'high';
  market: string;
  minCapital: number;
  maxSymbols: number;
  requiredParams: string[];
  optionalParams: string[];
  codeTemplate: string;
  tags: string[];
  metadata: {
    author: string;
    version: string;
    createdAt: string;
    updatedAt: string;
    usage_count: number;
    rating: number;
  };
}

export interface TemplateMatch {
  template: StrategyTemplate;
  matchScore: number;
  compatibilityScore: number;
  suggestions: string[];
  requiredModifications: string[];
}

export const availableTemplatesState = atom<StrategyTemplate[]>({
  key: 'availableTemplatesState',
  default: []
});

export const selectedTemplateState = atom<StrategyTemplate | null>({
  key: 'selectedTemplateState',
  default: null
});

export const templateMatchesState = atom<TemplateMatch[]>({
  key: 'templateMatchesState',
  default: []
});

// ==================== 验证相关状态 ====================

export interface ValidationError {
  field: string;
  rule: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
  suggestion?: string;
}

export interface ValidationResult {
  isValid: boolean;
  score?: number;
  errors: ValidationError[];
  warnings: ValidationError[];
  suggestions: string[];
  next_steps: string[];
}

export interface ParameterValidationResult extends ValidationResult {
  field: string;
  value: any;
  rule: string;
}

export interface CodeValidationResult extends ValidationResult {
  quality_score?: number;
  syntax_errors: ValidationError[];
  logic_errors: ValidationError[];
  complexity: 'low' | 'medium' | 'high';
  metrics: {
    lines_of_code: number;
    cyclomatic_complexity: number;
    maintainability_index: number;
  };
}

export interface TemplateValidationResult extends ValidationResult {
  template_id: string;
  compatibility_score: number;
  parameter_mapping: Record<string, any>;
}

export interface BatchValidationResult {
  success: boolean;
  overall_score: number;
  is_ready_for_generation: boolean;
  parameter_validation?: ParameterValidationResult;
  code_validation?: CodeValidationResult;
  template_validation?: TemplateValidationResult;
  processing_time: number;
  next_steps: string[];
}

export const parameterValidationState = atom<ParameterValidationResult | null>({
  key: 'parameterValidationState',
  default: null
});

export const codeValidationState = atom<CodeValidationResult | null>({
  key: 'codeValidationState',
  default: null
});

export const templateValidationState = atom<TemplateValidationResult | null>({
  key: 'templateValidationState',
  default: null
});

export const batchValidationState = atom<BatchValidationResult | null>({
  key: 'batchValidationState',
  default: null
});

export const realtimeValidationState = atom<boolean>({
  key: 'realtimeValidationState',
  default: true
});

// ==================== 性能监控状态 ====================

export interface ProviderPerformance {
  provider_name: string;
  model_name: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  avg_response_time: number;
  min_response_time: number;
  max_response_time: number;
  success_rate: number;
  error_rate: number;
  last_request_time: string;
  status: 'healthy' | 'degraded' | 'down';
}

export interface SystemPerformance {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  avg_response_time: number;
  active_providers: number;
  memory_usage?: number;
  cpu_usage?: number;
  uptime: number;
  last_updated: string;
}

export interface PerformanceAlert {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  provider_name: string;
  metric_name: string;
  current_value: number;
  threshold: number;
  created_at: string;
  resolved_at?: string;
  status: 'active' | 'resolved';
}

export const systemPerformanceState = atom<SystemPerformance | null>({
  key: 'systemPerformanceState',
  default: null
});

export const providerPerformanceState = atom<ProviderPerformance[]>({
  key: 'providerPerformanceState',
  default: []
});

export const performanceAlertsState = atom<PerformanceAlert[]>({
  key: 'performanceAlertsState',
  default: []
});

// ==================== 文件管理状态 ====================

export interface FileInfo {
  file_id: string;
  filename: string;
  content_type: string;
  size: number;
  file_path: string;
  upload_time: string;
  user_id: string;
  category: string;
  content_hash?: string;
  description?: string;
  tags?: string[];
}

export const userFilesState = atom<FileInfo[]>({
  key: 'userFilesState',
  default: []
});

export const selectedFileState = atom<FileInfo | null>({
  key: 'selectedFileState',
  default: null
});

export const fileUploadProgressState = atom<number>({
  key: 'fileUploadProgressState',
  default: 0
});

export const isFileUploadingState = atom<boolean>({
  key: 'isFileUploadingState',
  default: false
});

// ==================== API状态 ====================

export interface ApiStatus {
  isHealthy: boolean;
  lastChecked: string;
  responseTime: number;
  error?: string;
}

export const apiStatusState = atom<ApiStatus>({
  key: 'apiStatusState',
  default: {
    isHealthy: false,
    lastChecked: '',
    responseTime: 0
  }
});

export const apiLoadingState = atom<boolean>({
  key: 'apiLoadingState',
  default: false
});

export const apiErrorState = atom<string | null>({
  key: 'apiErrorState',
  default: null
});
