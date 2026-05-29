/**
 * OBV (On Balance Volume) 指标计算器
 * 能量潮 - 通过成交量变化衡量买卖压力
 */

export interface OBVResult {
  values: number[];
  timestamp: number[];
}

export interface VolumeData {
  close: number;
  volume: number;
  timestamp: number;
}

/**
 * 计算OBV指标
 * @param data 价格和成交量数据
 * @returns OBV结果
 */
export function calculateOBV(data: VolumeData[]): OBVResult {
  if (data.length < 2) {
    throw new Error('数据长度至少需要 2 个数据点');
  }

  const obvValues: number[] = [];
  const timestamps: number[] = [];

  // 初始OBV为0或第一个成交量
  let currentOBV = data[0].volume;
  obvValues.push(currentOBV);
  timestamps.push(data[0].timestamp);

  // 计算后续OBV值
  for (let i = 1; i < data.length; i++) {
    const current = data[i];
    const previous = data[i - 1];

    if (current.close > previous.close) {
      // 上涨日，加上成交量
      currentOBV += current.volume;
    } else if (current.close < previous.close) {
      // 下跌日，减去成交量
      currentOBV -= current.volume;
    }
    // 平盘日，OBV不变

    obvValues.push(currentOBV);
    timestamps.push(current.timestamp);
  }

  return {
    values: obvValues,
    timestamp: timestamps
  };
}

/**
 * 计算OBV的移动平均线
 * @param obv OBV数据
 * @param period 周期
 * @returns OBV均线
 */
export function calculateOBVMA(obv: number[], period: number): number[] {
  if (obv.length < period) {
    throw new Error(`数据长度至少需要 ${period} 个数据点`);
  }

  const ma: number[] = [];

  for (let i = period - 1; i < obv.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += obv[i - j];
    }
    ma.push(sum / period);
  }

  return ma;
}

/**
 * OBV背离检测
 * @param obvValues OBV值数组
 * @param prices 价格数组
 * @param lookback 回看周期
 * @returns 是否存在背离
 */
export function detectOBVDivergence(
  obvValues: number[],
  prices: number[],
  lookback: number = 20
): { bullish: boolean; bearish: boolean } {
  if (obvValues.length < lookback || prices.length < lookback) {
    return { bullish: false, bearish: false };
  }

  const recentOBV = obvValues.slice(-lookback);
  const recentPrices = prices.slice(-lookback);

  const obvTrend = recentOBV[recentOBV.length - 1] - recentOBV[0];
  const priceTrend = recentPrices[recentPrices.length - 1] - recentPrices[0];

  // 看涨背离：价格下跌但OBV上涨
  const bullish = priceTrend < 0 && obvTrend > 0;

  // 看跌背离：价格上涨但OBV下跌
  const bearish = priceTrend > 0 && obvTrend < 0;

  return { bullish, bearish };
}

/**
 * OBV指标解读
 * @param current 当前OBV值
 * @param previous 前一个OBV值
 * @param priceChange 价格变化
 * @returns 解读结果
 */
export function interpretOBV(
  current: number,
  previous: number,
  priceChange: number
): string {
  const obvChange = current - previous;

  if (priceChange > 0 && obvChange > 0) {
    return '价涨量增，看涨信号';
  } else if (priceChange > 0 && obvChange < 0) {
    return '价涨量减，可能见顶';
  } else if (priceChange < 0 && obvChange < 0) {
    return '价跌量增，看跌信号';
  } else if (priceChange < 0 && obvChange > 0) {
    return '价跌量减，可能见底';
  } else {
    return '横盘整理';
  }
}

export default {
  calculateOBV,
  calculateOBVMA,
  detectOBVDivergence,
  interpretOBV
};
