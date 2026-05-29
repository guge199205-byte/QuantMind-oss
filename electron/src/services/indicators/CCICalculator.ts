/**
 * CCI (Commodity Channel Index) 指标计算器
 * 顺势指标 - 衡量价格偏离平均价格的程度
 */

export interface CCIResult {
  values: number[];
  period: number;
  timestamp: number[];
  overbought: number[]; // 超买线（通常+100）
  oversold: number[]; // 超卖线（通常-100）
}

export interface CCIData {
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

/**
 * 计算CCI指标
 * @param data 高低收价数据
 * @param period 周期，默认20
 * @param overboughtLevel 超买水平，默认+100
 * @param oversoldLevel 超卖水平，默认-100
 * @returns CCI结果
 */
export function calculateCCI(
  data: CCIData[],
  period: number = 20,
  overboughtLevel: number = 100,
  oversoldLevel: number = -100
): CCIResult {
  if (data.length < period) {
    throw new Error(`数据长度至少需要 ${period} 个数据点`);
  }

  const typicalPrices: number[] = [];
  const cciValues: number[] = [];
  const timestamps: number[] = [];
  const overbought: number[] = [];
  const oversold: number[] = [];

  // 计算典型价格 TP = (high + low + close) / 3
  for (let i = 0; i < data.length; i++) {
    const tp = (data[i].high + data[i].low + data[i].close) / 3;
    typicalPrices.push(tp);
  }

  // 计算CCI
  for (let i = period - 1; i < data.length; i++) {
    // 计算TP的SMA
    let tpSum = 0;
    for (let j = 0; j < period; j++) {
      tpSum += typicalPrices[i - j];
    }
    const tpSMA = tpSum / period;

    // 计算平均偏差 (Mean Deviation)
    let mdSum = 0;
    for (let j = 0; j < period; j++) {
      mdSum += Math.abs(typicalPrices[i - j] - tpSMA);
    }
    const md = mdSum / period;

    // 计算CCI
    // CCI = (TP - SMA(TP)) / (0.015 * MD)
    const cci = md !== 0 ? (typicalPrices[i] - tpSMA) / (0.015 * md) : 0;

    cciValues.push(cci);
    timestamps.push(data[i].timestamp);
    overbought.push(overboughtLevel);
    oversold.push(oversoldLevel);
  }

  return {
    values: cciValues,
    period,
    timestamp: timestamps,
    overbought,
    oversold
  };
}

/**
 * 检测CCI信号
 * @param cci CCI结果
 * @param index 当前索引
 * @returns 信号类型
 */
export function detectCCISignal(
  cci: CCIResult,
  index: number
): 'buy' | 'sell' | 'overbought' | 'oversold' | 'neutral' {
  if (index < 1) return 'neutral';

  const current = cci.values[index];
  const previous = cci.values[index - 1];

  // 超买超卖区域
  if (current > cci.overbought[index]) {
    return 'overbought';
  } else if (current < cci.oversold[index]) {
    return 'oversold';
  }

  // 突破信号
  if (previous < cci.oversold[index - 1] && current > cci.oversold[index]) {
    return 'buy'; // 从超卖区向上突破
  } else if (previous > cci.overbought[index - 1] && current < cci.overbought[index]) {
    return 'sell'; // 从超买区向下突破
  }

  return 'neutral';
}

/**
 * CCI背离检测
 * @param cciValues CCI值数组
 * @param prices 价格数组
 * @param lookback 回看周期
 * @returns 背离类型
 */
export function detectCCIDivergence(
  cciValues: number[],
  prices: number[],
  lookback: number = 14
): { bullish: boolean; bearish: boolean; type: string } {
  if (cciValues.length < lookback || prices.length < lookback) {
    return { bullish: false, bearish: false, type: 'none' };
  }

  const recentCCI = cciValues.slice(-lookback);
  const recentPrices = prices.slice(-lookback);

  // 找到CCI和价格的极值
  const cciMax = Math.max(...recentCCI);
  const cciMin = Math.min(...recentCCI);
  const priceMax = Math.max(...recentPrices);
  const priceMin = Math.min(...recentPrices);

  const cciMaxIdx = recentCCI.indexOf(cciMax);
  const cciMinIdx = recentCCI.indexOf(cciMin);
  const priceMaxIdx = recentPrices.indexOf(priceMax);
  const priceMinIdx = recentPrices.indexOf(priceMin);

  // 看涨背离：价格创新低，但CCI未创新低
  const bullish = priceMinIdx > cciMinIdx && recentPrices[recentPrices.length - 1] < priceMin;

  // 看跌背离：价格创新高，但CCI未创新高
  const bearish = priceMaxIdx > cciMaxIdx && recentPrices[recentPrices.length - 1] > priceMax;

  let type = 'none';
  if (bullish) type = 'bullish';
  if (bearish) type = 'bearish';

  return { bullish, bearish, type };
}

/**
 * CCI指标解读
 * @param cciValue CCI值
 * @param overboughtLevel 超买水平
 * @param oversoldLevel 超卖水平
 * @returns 解读结果
 */
export function interpretCCI(
  cciValue: number,
  overboughtLevel: number = 100,
  oversoldLevel: number = -100
): string {
  if (cciValue > overboughtLevel * 2) {
    return '极度超买，警惕回调';
  } else if (cciValue > overboughtLevel) {
    return '超买区域，可能回调';
  } else if (cciValue > 0) {
    return '强势区域，上升趋势';
  } else if (cciValue > oversoldLevel) {
    return '弱势区域，下降趋势';
  } else if (cciValue > oversoldLevel * 2) {
    return '超卖区域，可能反弹';
  } else {
    return '极度超卖，关注反弹';
  }
}

export default {
  calculateCCI,
  detectCCISignal,
  detectCCIDivergence,
  interpretCCI
};
