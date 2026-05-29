/**
 * 共享枚举定义
 * 确保前端和后端使用相同的枚举值
 */

// 风险等级枚举
export const RISK_LEVELS = ['low', 'medium', 'high'] as const;
export type RiskLevel = typeof RISK_LEVELS[number];

// 市场类型枚举
export const MARKETS = ['CN', 'US', 'HK', 'GLOBAL'] as const;
export type MarketType = typeof MARKETS[number];

// 时间框架枚举
export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'] as const;
export type Timeframe = typeof TIMEFRAMES[number];

// 策略风格枚举
export const STRATEGY_STYLES = ['conservative', 'balanced', 'aggressive', 'custom'] as const;
export type StrategyStyle = typeof STRATEGY_STYLES[number];

// 策略长度枚举
export const STRATEGY_LENGTHS = ['short_term', 'medium_term', 'long_term', 'unlimited'] as const;
export type StrategyLength = typeof STRATEGY_LENGTHS[number];

// 回测周期枚举
export const BACKTEST_PERIODS = ['3months', '6months', '1year', '2years', '5years', 'unlimited'] as const;
export type BacktestPeriod = typeof BACKTEST_PERIODS[number];

// 策略类别枚举
export const STRATEGY_CATEGORIES = ['trend', 'mean_reversion', 'momentum', 'breakout', 'arbitrage'] as const;
export type StrategyCategory = typeof STRATEGY_CATEGORIES[number];

// 组件类型枚举
export const COMPONENT_TYPES = ['DATA_HANDLING', 'LOGIC', 'RISK_CONTROL', 'OPTIMIZATION'] as const;
export type ComponentType = typeof COMPONENT_TYPES[number];

// 验证错误类型枚举
export const VALIDATION_ERROR_TYPES = ['syntax', 'logic', 'dependency', 'parameter'] as const;
export type ValidationErrorType = typeof VALIDATION_ERROR_TYPES[number];

// 验证严重程度枚举
export const VALIDATION_SEVERITIES = ['error', 'warning', 'info'] as const;
export type ValidationSeverity = typeof VALIDATION_SEVERITIES[number];

// 消息角色枚举
export const MESSAGE_ROLES = ['user', 'assistant', 'system'] as const;
export type MessageRole = typeof MESSAGE_ROLES[number];

// 消息类型枚举
export const MESSAGE_TYPES = ['text', 'code', 'chart', 'error', 'suggestion'] as const;
export type MessageType = typeof MESSAGE_TYPES[number];

// 生成状态枚举
export const GENERATION_STATUSES = ['idle', 'validating', 'generating', 'completed', 'error'] as const;
export type GenerationStatus = typeof GENERATION_STATUSES[number];

// API响应代码枚举
export const API_CODES = {
  SUCCESS: 0,
  PARAM_REQUIRED: 1001,
  PARAM_INVALID: 1002,
  STRATEGY_GEN_FAILED: 2001,
  NOT_FOUND: 2002,
  FILE_NOT_FOUND: 2003,
  INTERNAL_ERROR: 5000
} as const;

export type ApiCode = typeof API_CODES[keyof typeof API_CODES];

// 导出枚举值常量
export const ENUM_CONSTANTS = {
  RISK_LEVELS,
  MARKETS,
  TIMEFRAMES,
  STRATEGY_STYLES,
  STRATEGY_LENGTHS,
  BACKTEST_PERIODS,
  STRATEGY_CATEGORIES,
  COMPONENT_TYPES,
  VALIDATION_ERROR_TYPES,
  VALIDATION_SEVERITIES,
  MESSAGE_ROLES,
  MESSAGE_TYPES,
  GENERATION_STATUSES,
  API_CODES
} as const;

// 枚举验证函数
export const isValidRiskLevel = (value: string): value is RiskLevel => {
  return RISK_LEVELS.includes(value as RiskLevel);
};

export const isValidMarket = (value: string): value is MarketType => {
  return MARKETS.includes(value as MarketType);
};

export const isValidTimeframe = (value: string): value is Timeframe => {
  return TIMEFRAMES.includes(value as Timeframe);
};

export const isValidStrategyStyle = (value: string): value is StrategyStyle => {
  return STRATEGY_STYLES.includes(value as StrategyStyle);
};

export const isValidStrategyLength = (value: string): value is StrategyLength => {
  return STRATEGY_LENGTHS.includes(value as StrategyLength);
};

export const isValidBacktestPeriod = (value: string): value is BacktestPeriod => {
  return BACKTEST_PERIODS.includes(value as BacktestPeriod);
};

export const isValidStrategyCategory = (value: string): value is StrategyCategory => {
  return STRATEGY_CATEGORIES.includes(value as StrategyCategory);
};

// 枚举默认值
export const DEFAULT_ENUM_VALUES = {
  RISK_LEVEL: 'medium' as RiskLevel,
  MARKET: 'CN' as MarketType,
  TIMEFRAME: '1d' as Timeframe,
  STRATEGY_STYLE: 'custom' as StrategyStyle,
  STRATEGY_LENGTH: 'unlimited' as StrategyLength,
  BACKTEST_PERIOD: '1year' as BacktestPeriod,
  STRATEGY_CATEGORY: 'trend' as StrategyCategory,
  COMPONENT_TYPE: 'LOGIC' as ComponentType,
  VALIDATION_SEVERITY: 'error' as ValidationSeverity,
  MESSAGE_ROLE: 'user' as MessageRole,
  MESSAGE_TYPE: 'text' as MessageType,
  GENERATION_STATUS: 'idle' as GenerationStatus
} as const;
