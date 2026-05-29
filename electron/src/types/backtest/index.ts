/**
 * 回测系统类型定义
 */

export * from './qlib';

export interface OHLCV {
  date: string;
  /** unix ms timestamp - 兼容部分模块使用 timestamp */
  timestamp?: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Trade {
  /** 可选 id */
  id?: string;
  date?: string;
  timestamp?: number;
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  amount?: number;
  commission?: number;
  slippage?: number;
  pnl?: number;
  cumulativePnL?: number;
}

// 保留部分基础类型以兼容现有代码，后续可逐步移除
export interface StrategyParameter {
  name: string;
  type: 'number' | 'string' | 'boolean';
  value: any;
  min?: number;
  max?: number;
  step?: number;
  description?: string;
}

export interface Strategy {
  name: string;
  version: string;
  description?: string;
  parameters: StrategyParameter[];
  code?: string;
  // 移除复杂的 context 和函数定义
  initialize?: (context: any) => void;
  onBar?: (bar: OHLCV, context: any) => void;
  finalize?: (context: any) => void;
}

/** 回测配置 */
export interface BacktestConfig {
  symbol?: string;
  startDate?: string;
  endDate?: string;
  initialCapital: number;
  commission?: number;
  slippage?: number;
  leverage?: number;
  riskPerTrade?: number;
}

export interface BacktestResult {
  config: BacktestConfig;
  trades: Trade[];
  equity: any;
  metrics: any;
  drawdown?: any;
  startTime?: number;
  endTime?: number;
  executionTime?: number;
}

export interface OrderRequest {
  type: 'market' | 'limit' | 'stop';
  side: 'buy' | 'sell';
  size: number;
  price?: number;
  stopPrice?: number;
}

export interface OrderExecution {
  orderId: string;
  executionPrice: number;
  executionSize: number;
  commission: number;
  slippage: number;
  timestamp: number;
}

export interface Position {
  symbol: string;
  size: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL?: number;
  realizedPnL?: number;
}

export interface IndicatorManager {
  sma: (period: number) => number[];
  ema: (period: number) => number[];
  rsi: (period: number) => number[];
  macd: () => { macd: number[]; signal: number[]; histogram: number[] };
  bollinger: (period: number, stdDev: number) => { upper: number[]; middle: number[]; lower: number[] };
  atr: (period: number) => number[];
  obv: () => number[];
}

export interface StrategyContext {
  buy: (size: number, price?: number) => void;
  sell: (size: number, price?: number) => void;
  closePosition: () => void;
  position: Position | null;
  capital: number;
  equity: number;
  indicators: IndicatorManager;
  bars: OHLCV[];
  currentBar?: OHLCV;
  barIndex: number;
}

export interface EquityCurve {
  timestamps: number[];
  values: number[];
  drawdowns: number[];
  returns: number[];
}

export interface DrawdownPeriod {
  start: number;
  end: number;
  peak: number;
  trough: number;
  drawdown: number;
  duration: number;
  recovery?: number;
}

export interface DrawdownAnalysis {
  maxDrawdown: number;
  maxDrawdownDuration: number;
  drawdownPeriods: DrawdownPeriod[];
}

export interface PerformanceMetrics {
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  maxDrawdownDuration?: number;
  winRate: number;
  profitFactor: number;
  averageWin: number;
  averageLoss: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  dailyReturns: number[];
  weeklyReturns: number[];
  monthlyReturns: number[];
}
