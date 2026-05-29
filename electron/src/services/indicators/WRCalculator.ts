/**
 * WR (Williams %R) 指标计算器
 * 威廉指标 - 衡量超买超卖的震荡指标
 */

export interface WRResult {
  values: number[];
  period: number;
  timestamp: number[];
  overbought: number[]; // 超买线（通常-20）
  oversold: number[]; // 超卖线（通常-80）
}

export interface WRData {
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

/**
 * 计算WR指标
 * @param data 高低收价数据
 * @param period 周期，默认14
 * @param overboughtLevel 超买水平，默认-20
 * @param oversoldLevel 超卖水平，默认-80
 * @returns WR结果
 */
export function calculateWR(
  data: WRData[],
  period: number = 14,
  overboughtLevel: number = -20,
  oversoldLevel: number = -80
): WRResult {
  if (data.length < period) {
    throw new Error(`数据长度至少需要 ${period} 个数据点`);
  }

  const wrValues: number[] = [];
  const timestamps: number[] = [];
  const overbought: number[] = [];
  const oversold: number[] = [];

  // 计算WR
  for (let i = period - 1; i < data.length; i++) {
    // 找到周期内的最高价和最低价
    let highestHigh = data[i].high;
    let lowestLow = data[i].low;

    for (let j = 0; j < period; j++) {
      const idx = i - j;
      highestHigh = Math.max(highestHigh, data[idx].high);
      lowestLow = Math.min(lowestLow, data[idx].low);
    }

    // 计算WR
    // WR = (highest_high - close) / (highest_high - lowest_low) * -100
    const range = highestHigh - lowestLow;
    const wr = range !== 0
      ? ((highestHigh - data[i].close) / range) * -100
      : -50; // 如果范围为0，返回中间值

    wrValues.push(wr);
    timestamps.push(data[i].timestamp);
    overbought.push(overboughtLevel);
    oversold.push(oversoldLevel);
  }

  return {
    values: wrValues,
    period,
    timestamp: timestamps,
    overbought,
    oversold
  };
}

/**
 * 检测WR信号
 * @param wr WR结果
 * @param index 当前索引
 * @returns 信号类型
 */
export function detectWRSignal(
  wr: WRResult,
  index: number
): 'buy' | 'sell' | 'overbought' | 'oversold' | 'neutral' {
  if (index < 1) return 'neutral';

  const current = wr.values[index];
  const previous = wr.values[index - 1];

  // 超买超卖状态
  if (current > wr.overbought[index]) {
    return 'overbought';
  } else if (current < wr.oversold[index]) {
    return 'oversold';
  }

  // 信号检测
  if (previous < wr.oversold[index - 1] && current > wr.oversold[index]) {
    return 'buy'; // 从超卖区向上突破
  } else if (previous > wr.overbought[index - 1] && current < wr.overbought[index]) {
    return 'sell'; // 从超买区向下突破
  }

  return 'neutral';
}

/**
 * 计算WR的SMA
 * @param wrValues WR值数组
 * @param period 周期
 * @returns WR均线
 */
export function calculateWRSMA(wrValues: number[], period: number): number[] {
  if (wrValues.length < period) {
    throw new Error(`数据长度至少需要 ${period} 个数据点`);
  }

  const sma: number[] = [];

  for (let i = period - 1; i < wrValues.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += wrValues[i - j];
    }
    sma.push(sum / period);
  }

  return sma;
}

/**
 * WR背离检测
 * @param wrValues WR值数组
 * @param prices 价格数组
 * @param lookback 回看周期
 * @returns 背离信息
 */
export function detectWRDivergence(
  wrValues: number[],
  prices: number[],
  lookback: number = 14
): { bullish: boolean; bearish: boolean; strength: number } {
  if (wrValues.length < lookback || prices.length < lookback) {
    return { bullish: false, bearish: false, strength: 0 };
  }

  const recentWR = wrValues.slice(-lookback);
  const recentPrices = prices.slice(-lookback);

  // 计算趋势
  const wrTrend = recentWR[recentWR.length - 1] - recentWR[0];
  const priceTrend = recentPrices[recentPrices.length - 1] - recentPrices[0];

  // 看涨背离：价格下跌但WR上涨
  const bullish = priceTrend < 0 && wrTrend > 0;

  // 看跌背离：价格上涨但WR下跌
  const bearish = priceTrend > 0 && wrTrend < 0;

  // 计算背离强度
  const strength = Math.abs(wrTrend) / 100;

  return { bullish, bearish, strength };
}

/**
 * WR指标解读
 * @param wrValue WR值
 * @param overboughtLevel 超买水平
 * @param oversoldLevel 超卖水平
 * @returns 解读结果
 */
export function interpretWR(
  wrValue: number,
  overboughtLevel: number = -20,
  oversoldLevel: number = -80
): string {
  if (wrValue > -10) {
    return '极度超买，高位风险';
  } else if (wrValue > overboughtLevel) {
    return '超买区域，注意回调';
  } else if (wrValue > -50) {
    return '强势区域，多头占优';
  } else if (wrValue > oversoldLevel) {
    return '弱势区域，空头占优';
  } else if (wrValue > -90) {
    return '超卖区域，关注反弹';
  } else {
    return '极度超卖，反弹机会';
  }
}

/**
 * 多周期WR分析
 * @param data 价格数据
 * @param periods 多个周期
 * @returns 多周期WR结果
 */
export function calculateMultiPeriodWR(
  data: WRData[],
  periods: number[] = [6, 10, 14]
): Map<number, WRResult> {
  const results = new Map<number, WRResult>();

  for (const period of periods) {
    if (data.length >= period) {
      const wr = calculateWR(data, period);
      results.set(period, wr);
    }
  }

  return results;
}

export default {
  calculateWR,
  detectWRSignal,
  calculateWRSMA,
  detectWRDivergence,
  interpretWR,
  calculateMultiPeriodWR
};
