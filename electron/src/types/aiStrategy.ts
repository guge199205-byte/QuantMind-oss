/**
 * AI策略相关类型定义
 * 独立于Strategy接口的类型定义
 */

import {
  StrategyStyle,
  StrategyLength,
  BacktestPeriod,
  MarketType,
  Timeframe,
  RiskLevel
} from './strategy';

// 股票池类型
export type StockPoolType = 'predefined' | 'dynamic' | 'custom';

// 预设股票池键名
export type PredefinedPoolKey = 'default' | 'large_cap' | 'tech' | 'finance' | 'defensive' | 'balanced';

// 动态筛选条件
export interface DynamicStockPoolConditions {
  // 行业筛选
  industry?: string[];
  // 技术指标筛选
  technical?: {
    rsi?: { min?: number; max?: number };
    volume?: { min_avg?: number };
    price?: { min?: number; max?: number };
    ma?: { period?: number; above?: boolean };
  };
  // 基本面筛选
  fundamental?: {
    market_cap?: { min?: number; max?: number };
    pe_ratio?: { min?: number; max?: number };
    roe?: { min?: number };
    revenue_growth?: { min?: number };
    debt_ratio?: { max?: number };
  };
  // 其他条件
  limit?: number; // 结果数量限制
}

// 股票池配置
export interface StockPoolConfig {
  type: StockPoolType;
  predefinedKey?: PredefinedPoolKey;
  conditions?: DynamicStockPoolConditions;
  customSymbols?: string[];
  resolvedSymbols: string[];
  lastUpdated?: string;
  isLoading: boolean;
  error?: string | null;
  metadata?: {
    poolName?: string;
    description?: string;
    source?: string;
  };
}

// 股票池信息（用于展示）
export interface StockPoolInfo {
  key: PredefinedPoolKey;
  name: string;
  description: string;
  count: number;
  category: string;
  riskLevel: RiskLevel;
}

// AI策略参数
export interface AIStrategyParams {
  description: string;
  style: StrategyStyle;
  strategyLength: StrategyLength;
  backtestPeriod: BacktestPeriod;
  market: MarketType;
  riskLevel: RiskLevel;
  symbols: string[];
  timeframe: Timeframe;
  initialCapital: number;
  positionSize: number;
  maxPositions: number;
  stopLoss: number;
  takeProfit: number;
  maxDrawdown?: number;
  commissionRate?: number;
  slippage?: number;
  benchmark?: string;
  // 新增股票池配置
  stockPool?: StockPoolConfig;
}

// AI策略聊天消息
export interface AIStrategyChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  type?: 'text' | 'code' | 'chart' | 'error' | 'suggestion';
  metadata?: Record<string, any>;
}

// AI策略模板
export interface AIStrategyTemplate {
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

// AI策略接口
export interface AIStrategy {
  id: string;
  name: string;
  description: string;
  code: string;
  parameters: AIStrategyParams;
  status: 'draft' | 'active' | 'archived';
  metadata: any;
  conversation: AIStrategyChatMessage[];
  template?: AIStrategyTemplate;
  validation?: any;
  analysis?: any;
  language?: string;
  framework?: string;
  // 新增缺失的属性
  strategy_name?: string;
  strategy_code?: string;
  rationale?: string;
  artifacts?: any[];
  createdAt?: string;
  updatedAt?: string;
}
