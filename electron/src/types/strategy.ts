/**
 * 策略相关类型定义
 * 基于前端改进规划文档实现的类型系统
 * 使用共享枚举确保前后端一致性
 */

// 本地枚举定义 - 临时解决方案
export type RiskLevel = 'low' | 'medium' | 'high';
export type MarketType = 'CN' | 'US' | 'HK' | 'GLOBAL';
export type Timeframe = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w' | '1M';
export type StrategyStyle = 'conservative' | 'balanced' | 'aggressive' | 'custom';
export type StrategyLength = 'short_term' | 'medium_term' | 'long_term' | 'unlimited';
export type BacktestPeriod = '3months' | '6months' | '1year' | '2years' | '5years' | 'unlimited';
export type StrategyCategory = 'trend' | 'mean_reversion' | 'momentum' | 'breakout' | 'arbitrage' | 'custom';
export type ComponentType = 'DATA_HANDLING' | 'LOGIC' | 'RISK_CONTROL' | 'OPTIMIZATION' | 'ENTRY' | 'EXIT' | 'RISK';
export type ValidationErrorType = 'syntax' | 'logic' | 'dependency' | 'parameter';
export type ValidationSeverity = 'error' | 'warning' | 'info';
export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageType = 'text' | 'code' | 'chart' | 'error' | 'suggestion';
export type GenerationStatus = 'idle' | 'validating' | 'generating' | 'completed' | 'error';

// 常量定义
export const RISK_LEVELS = ['low', 'medium', 'high'];
export const MARKETS = ['CN', 'US', 'HK', 'GLOBAL'];
export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'];
export const STRATEGY_STYLES = ['conservative', 'balanced', 'aggressive', 'custom'];
export const STRATEGY_LENGTHS = ['short_term', 'medium_term', 'long_term', 'unlimited'];
export const BACKTEST_PERIODS = ['3months', '6months', '1year', '2years', '5years', 'unlimited'];
export const STRATEGY_CATEGORIES = ['trend', 'mean_reversion', 'momentum', 'breakout', 'arbitrage', 'custom'];
export const COMPONENT_TYPES = ['DATA_HANDLING', 'LOGIC', 'RISK_CONTROL', 'OPTIMIZATION', 'ENTRY', 'EXIT', 'RISK'];

export const DEFAULT_ENUM_VALUES = {
  riskLevel: 'medium' as RiskLevel,
  market: 'CN' as MarketType,
  timeframe: '1d' as Timeframe,
  strategyStyle: 'custom' as StrategyStyle,
  strategyLength: 'unlimited' as StrategyLength,
  backtestPeriod: '1year' as BacktestPeriod,
  strategyCategory: 'custom' as StrategyCategory,
  componentType: 'LOGIC' as ComponentType
};

// 验证函数
export const isValidRiskLevel = (value: string): value is RiskLevel => {
  return RISK_LEVELS.includes(value);
};

export const isValidMarket = (value: string): value is MarketType => {
  return MARKETS.includes(value);
};

export const isValidTimeframe = (value: string): value is Timeframe => {
  return TIMEFRAMES.includes(value);
};

export const isValidStrategyStyle = (value: string): value is StrategyStyle => {
  return STRATEGY_STYLES.includes(value);
};

export const isValidStrategyLength = (value: string): value is StrategyLength => {
  return STRATEGY_LENGTHS.includes(value);
};

export const isValidBacktestPeriod = (value: string): value is BacktestPeriod => {
  return BACKTEST_PERIODS.includes(value);
};

export const isValidStrategyCategory = (value: string): value is StrategyCategory => {
  return STRATEGY_CATEGORIES.includes(value);
};

// 验证规则
export interface ValidationRule {
  field: string;
  required: boolean;
  type: 'string' | 'number' | 'array' | 'boolean';
  min?: number;
  max?: number;
  pattern?: RegExp;
  custom?: (value: any) => boolean | string;
}

// 策略组件验证
export interface ComponentValidation {
  requiredParams: string[];
  validationRules: ValidationRule[];
  dependencies: string[];
}

// 策略组件
export interface StrategyComponent {
  type: ComponentType;
  name: string;
  codeTemplate: string;
  requiredParams: string[];
  validation: ComponentValidation;
  description: string;
  required?: boolean;
  parameters?: Record<string, any>;
}

// 策略模板
export interface StrategyTemplate {
  id: string;
  name: string;
  category: StrategyCategory;
  description: string;
  version: string;
  author: string;
  createdAt: Date;
  updatedAt: Date;

  // 模板特性
  tags: string[];
  suitableMarkets: MarketType[];
  suitableTimeframes: Timeframe[];
  suitableRiskLevels: RiskLevel[];
  minCapital: number;
  maxSymbols: number;

  // 必需组件
  requiredComponents: StrategyComponent[];

  // 默认参数
  defaultParameters: Partial<StrategyParams>;

  // 验证规则
  validationRules: ValidationRule[];

  // 策略代码模板
  codeTemplate: string;

  // 模板元数据
  metadata: {
    complexity: 'low' | 'medium' | 'high';
    estimatedBacktestTime: string;
    dependencies: string[];
    performance: {
      expectedReturn: string;
      maxDrawdown: string;
      sharpeRatio: string;
    };
  };
}

// 策略参数
export interface StrategyParams {
  description: string;
  market: MarketType;
  riskLevel: RiskLevel;
  style: StrategyStyle;
  symbols: string[];
  timeframe: Timeframe;
  strategyLength: StrategyLength;
  backtestPeriod: BacktestPeriod;
  initialCapital: number;
  positionSize: number;
  maxPositions: number;
  stopLoss: number;
  takeProfit: number;
  maxDrawdown?: number;
  commissionRate?: number;
  slippage?: number;
  benchmark?: string;

  // 新增属性
  stockPoolConfig?: any;
  framework?: string;
  outputFormat?: string;
}

// 参数映射配置
export interface ParameterMapping {
  riskLevel: {
    [K in RiskLevel]: {
      stopLoss: number;
      takeProfit: number;
      maxDrawdown: number;
      positionSize: number;
      maxPositions: number;
    };
  };
  timeframe: {
    [K in Timeframe]: {
      dataRequired: 'tick' | 'minute' | 'daily' | 'weekly' | 'monthly';
      lookbackPeriod: number;
      minDataPoints: number;
    };
  };
  market: {
    [K in MarketType]: {
      tradingHours: string;
      currency: string;
      timezone: string;
      marginRate: number;
    };
  };
}

// 验证结果
export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

// 参数验证结果
export interface ParameterValidationResult extends ValidationResult {
  parameters?: Record<string, any>;
  issues?: Array<{
    parameter: string;
    issue: string;
    severity: 'error' | 'warning';
  }>;
}

// 提供商性能指标
export interface ProviderPerformance {
  provider: string;
  avgResponseTime: number;
  successRate: number;
  errorCount: number;
  requestCount: number;
  lastUpdate: string;
}

// 系统性能指标
export interface SystemPerformance {
  totalRequests: number;
  avgResponseTime: number;
  errorRate: number;
  providerStats: ProviderPerformance[];
  timestamp: string;
}

// 性能告警
export interface PerformanceAlert {
  id: string;
  type: 'slow_response' | 'high_error_rate' | 'provider_down';
  provider?: string;
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  resolved: boolean;
}

// 文件信息
export interface FileInfo {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadTime: string;
  url?: string;
  metadata?: Record<string, any>;
}

// 验证上下文
export interface ValidationContext {
  template?: StrategyTemplate;
  userParams: StrategyParams;
  market: MarketType;
  timeframe: Timeframe;
}

// 代码分析结果
export interface CodeAnalysis {
  missingRiskControls: string[];
  performanceIssues: string[];
  dataValidationGaps: string[];
  errorHandling: string[];
  dependencies: string[];
  complexity: number;
  maintainability: number;
}

// 优化目标
export type OptimizationGoal =
  | 'improve_performance'
  | 'add_risk_control'
  | 'fix_bugs'
  | 'enhance_readability'
  | 'add_data_validation'
  | 'optimize_logic';

// 用户意图分类
export type UserIntent =
  | 'optimize_performance'
  | 'add_features'
  | 'fix_errors'
  | 'modify_parameters'
  | 'clarify_logic';

// 优化建议
export interface Suggestion {
  type: OptimizationGoal;
  priority: 'high' | 'medium' | 'low';
  description: string;
  template?: string;
  parameters?: Record<string, any>;
}

// 反馈模板
export interface FeedbackTemplate {
  type: OptimizationGoal;
  template: string;
  parameters: string[];
  examples: string[];
}

// 对话消息
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  type: 'text' | 'code' | 'chart' | 'error' | 'suggestion';
  metadata?: {
    template?: string;
    validation?: ValidationResult;
    analysis?: CodeAnalysis;
    suggestions?: Suggestion[];
  };
}

// 策略元数据
export interface StrategyMetadata {
  createdAt: Date;
  updatedAt: Date;
  version: number;
  tags: string[];
  rationale?: string;
  factors?: string[];
  riskControls?: string[];
  assumptions?: string[];
  notes?: string;
  complexity?: number;
  estimatedPerformance?: {
    expectedReturn: number;
    expectedDrawdown: number;
    sharpeRatio: number;
    winRate: number;
  };
}

// 完整策略
export interface Strategy {
  id: string;
  name: string;
  description: string;
  code: string;
  parameters: StrategyParams;
  template?: StrategyTemplate;
  metadata: StrategyMetadata;
  conversation: ChatMessage[];
  validation?: ValidationResult;
  analysis?: CodeAnalysis;
}

// 回测结果
export interface BacktestResult {
  id: string;
  strategyId: string;
  parameters: StrategyParams;
  performance: {
    totalReturn: number;
    annualizedReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    profitFactor: number;
    calmarRatio: number;
    sortinoRatio: number;
  };
  trades: Trade[];
  equity: EquityPoint[];
  charts: {
    equity: string;
    drawdown: string;
    returns: string;
    monthly: string;
  };
  statistics: {
    totalTrades: number;
    winningTrades: number;
    losingTrades: number;
    avgWin: number;
    avgLoss: number;
    largestWin: number;
    largestLoss: number;
    avgTradeDuration: number;
    profitFactor: number;
  };
}

// 交易记录
export interface Trade {
  id: string;
  symbol: string;
  type: 'buy' | 'sell';
  quantity: number;
  price: number;
  timestamp: Date;
  commission: number;
  pnl?: number;
  exitReason?: 'stop_loss' | 'take_profit' | 'signal' | 'manual';
}

// 权益曲线点
export interface EquityPoint {
  timestamp: Date;
  equity: number;
  drawdown: number;
  returns: number;
}

// 生成结果
export interface GenerationResult {
  success: boolean;
  strategy?: Strategy;
  errors: string[];
  warnings: string[];
  suggestions: Suggestion[];
  processingTime: number;
}

// 模板匹配结果
export interface TemplateMatch {
  template: StrategyTemplate;
  confidence: number;
  reason: string;
  adaptations: string[];
}

// 生成阶段
export interface GenerationStage {
  name: string;
  code: string;
  type: 'framework' | 'imports' | 'data_handling' | 'logic' | 'risk_control' | 'optimization';
  order: number;
  required: boolean;
  context: ValidationContext;
  validation?: ValidationResult;
  dependencies: string[];
}

// 实时验证请求
export interface RealTimeValidationRequest {
  code: string;
  context: ValidationContext;
  stage?: string;
}

// 实时验证响应
export interface RealTimeValidationResponse {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  suggestions: string[];
  processingTime: number;
}

// 验证错误
export interface ValidationError {
  line: number;
  column: number;
  message: string;
  type: 'syntax' | 'logic' | 'dependency' | 'parameter';
  severity: 'error' | 'warning';
}

// 验证警告
export interface ValidationWarning {
  line: number;
  column: number;
  message: string;
  type: 'performance' | 'style' | 'best_practice';
  suggestion?: string;
}
