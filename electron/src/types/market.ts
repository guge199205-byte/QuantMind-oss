/**
 * 市场数据类型定义
 */

/**
 * 实时行情数据
 */
export interface MarketQuote {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  changePercent: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  time: string;
}

/**
 * 市场数据查询参数
 */
export interface MarketDataParams {
  symbols: string[];
  fields?: string[];
}

/**
 * 技术指标计算参数
 */
export interface IndicatorParams {
  symbol: string;
  indicators: string[];
  params?: Record<string, any>;
}

/**
 * 技术指标响应数据
 */
export interface IndicatorResponse {
  symbol: string;
  indicators: Record<string, any>;
  timestamp: string;
}

/**
 * 批量技术指标响应
 */
export interface BatchIndicatorResponse {
  results: IndicatorResponse[];
  failed: string[];
}
