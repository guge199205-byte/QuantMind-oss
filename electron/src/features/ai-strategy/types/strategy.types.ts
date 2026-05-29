/**
 * AI策略模块类型定义
 * 支持MiniQMT语法
 */

import { AIStrategyParams, AIStrategy } from '../../../store/slices/aiStrategySlice';
import { StrategyStyle } from '../../../types/strategy';

// MiniQMT support has been removed
// Placeholder type for MiniQMTValidationResult
export interface MiniQMTValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

// 策略生成参数
export interface AIStrategyGenerationParams extends Partial<Omit<AIStrategyParams, 'market' | 'riskLevel' | 'timeframe'>> {
  // 基础参数（从StrategyParams继承但使用不同的字段名）
  description: string;
  marketType: 'stock' | 'futures' | 'forex' | 'crypto';
  riskPreference: 'conservative' | 'moderate' | 'aggressive';
  investmentStyle: 'value' | 'growth' | 'balanced' | 'technical';
  timeframe: 'intraday' | 'daily' | 'weekly' | 'monthly';
  style: StrategyStyle; // 添加缺少的style属性

  // 股票池参数（新增）
  symbols: string[]; // 股票代码列表
  symbolsCount?: number; // 股票数量（用于验证）

  // 高级参数
  initialCapital?: number;
  maxPositions?: number;
  stopLoss?: number;
  takeProfit?: number;
  leverage?: number;
  maxDrawdown?: number; // 最大回撤限制
  commissionRate?: number; // 手续费率
  slippage?: number; // 滑点
  benchmark?: string; // 基准指数

  // 策略类型
  strategyType?: 'trend_following' | 'mean_reversion' | 'arbitrage' | 'market_making';
  strategyLength?: 'short_term' | 'medium_term' | 'long_term' | 'unlimited';
  backtestPeriod?: '3months' | '6months' | '1year' | '2years' | '5years';

  // MiniQMT相关参数
  framework?: 'standard' | 'miniqmt'; // 策略框架
  outputFormat?: 'python' | 'miniqmt'; // 输出格式
  includeImports?: boolean; // 是否包含导入语句
  includeComments?: boolean; // 是否包含注释

  // 模板相关
  templateId?: string; // 使用的模板ID
  useTemplate?: boolean; // 是否使用模板

  // 示例数据
  examples?: string[];
  referenceStrategies?: string[];
}

// 策略生成状态
export interface GenerationState {
  status: 'idle' | 'generating' | 'success' | 'error';
  progress: number;
  message: string;
  result?: AIStrategy;
  error?: string;
  framework?: 'standard' | 'miniqmt';
  validation?: MiniQMTValidationResult;
}

// MiniQMT策略结果
export interface MiniQMTStrategyResult {
  strategy_code: string;
  framework: 'miniqmt';
  validation: MiniQMTValidationResult;
  extracted_parameters: Record<string, any>;
  metadata: {
    generated_at: string;
    template_used?: string;
    complexity: 'beginner' | 'intermediate' | 'advanced';
    indicators: string[];
  };
}

// 参数面板配置
export interface ParameterPanelConfig {
  title: string;
  description: string;
  fields: ParameterField[];
  validation?: ValidationRule[];
}

export interface ParameterField {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'number' | 'range' | 'switch';
  required?: boolean;
  placeholder?: string;
  options?: Option[];
  min?: number;
  max?: number;
  step?: number;
  defaultValue?: any;
  validation?: ValidationRule[];
}

export interface Option {
  label: string;
  value: string;
  description?: string;
}

export interface ValidationRule {
  type: 'required' | 'minLength' | 'maxLength' | 'min' | 'max' | 'pattern';
  value?: any;
  message: string;
}

// 策略显示配置
export interface StrategyDisplayConfig {
  showCode: boolean;
  showParameters: boolean;
  showPerformance: boolean;
  showChart: boolean;
  layout: 'vertical' | 'horizontal' | 'grid';
}

// 策略分析结果
export interface StrategyAnalysis {
  id: string;
  strategyId: string;
  analysisType: 'backtest' | 'risk' | 'performance' | 'optimization';
  results: AnalysisResult[];
  createdAt: string;
}

export interface AnalysisResult {
  metric: string;
  value: number;
  unit?: string;
  description?: string;
  benchmark?: number;
}

// 策略模板
export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  parameters: Partial<AIStrategyGenerationParams>;
  code: string;
  tags: string[];
  usage: number;
  rating: number;
}

// 策略执行状态
export interface StrategyExecution {
  id: string;
  strategyId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  startTime: string;
  endTime?: string;
  progress: number;
  logs: ExecutionLog[];
  results?: any;
}

export interface ExecutionLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  data?: any;
}

// 策略比较
export interface StrategyComparison {
  strategies: AIStrategy[];
  metrics: string[];
  results: ComparisonResult[];
}

export interface ComparisonResult {
  strategyId: string;
  metric: string;
  value: number;
  rank: number;
}

// 导出配置
export interface StrategyExportConfig {
  format: 'python' | 'javascript' | 'json' | 'csv';
  includeCode: boolean;
  includeParameters: boolean;
  includePerformance: boolean;
  includeDocumentation: boolean;
}

// 策略分享
export interface StrategyShare {
  id: string;
  strategyId: string;
  sharedBy: string;
  sharedAt: string;
  visibility: 'public' | 'private' | 'unlisted';
  description: string;
  tags: string[];
  downloads: number;
  likes: number;
  comments: StrategyComment[];
}

export interface StrategyComment {
  id: string;
  userId: string;
  username: string;
  content: string;
  createdAt: string;
  likes: number;
}
