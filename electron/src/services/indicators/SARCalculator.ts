/**
 * SAR (Parabolic SAR) 指标计算器
 * 抛物线转向指标 - 用于判断趋势和止损点
 */

export interface SARResult {
  values: number[];
  trend: ('up' | 'down')[];
  timestamp: number[];
  af: number[]; // 加速因子历史
}

export interface SARData {
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

/**
 * 计算SAR指标
 * @param data 高低价数据
 * @param initialAF 初始加速因子，默认0.02
 * @param maxAF 最大加速因子，默认0.2
 * @param afIncrement AF增量，默认0.02
 * @returns SAR结果
 */
export function calculateSAR(
  data: SARData[],
  initialAF: number = 0.02,
  maxAF: number = 0.2,
  afIncrement: number = 0.02
): SARResult {
  if (data.length < 3) {
    throw new Error('数据长度至少需要 3 个数据点');
  }

  const sarValues: number[] = [];
  const trends: ('up' | 'down')[] = [];
  const timestamps: number[] = [];
  const afHistory: number[] = [];

  // 初始化
  let isUpTrend = data[1].close > data[0].close;
  let sar = isUpTrend ? data[0].low : data[0].high;
  let ep = isUpTrend ? data[0].high : data[0].low; // 极值点
  let af = initialAF;

  sarValues.push(sar);
  trends.push(isUpTrend ? 'up' : 'down');
  timestamps.push(data[0].timestamp);
  afHistory.push(af);

  // 计算后续SAR值
  for (let i = 1; i < data.length; i++) {
    const current = data[i];

    // 计算新的SAR值
    const newSAR = sar + af * (ep - sar);

    // 检查是否需要反转
    let needReverse = false;

    if (isUpTrend) {
      // 上升趋势
      if (current.low < newSAR) {
        needReverse = true;
      } else {
        sar = newSAR;
        // 确保SAR不高于前两根K线的最低价
        const prevLow1 = data[i - 1].low;
        const prevLow2 = i > 1 ? data[i - 2].low : prevLow1;
        sar = Math.min(sar, prevLow1, prevLow2);

        // 更新EP和AF
        if (current.high > ep) {
          ep = current.high;
          af = Math.min(af + afIncrement, maxAF);
        }
      }
    } else {
      // 下降趋势
      if (current.high > newSAR) {
        needReverse = true;
      } else {
        sar = newSAR;
        // 确保SAR不低于前两根K线的最高价
        const prevHigh1 = data[i - 1].high;
        const prevHigh2 = i > 1 ? data[i - 2].high : prevHigh1;
        sar = Math.max(sar, prevHigh1, prevHigh2);

        // 更新EP和AF
        if (current.low < ep) {
          ep = current.low;
          af = Math.min(af + afIncrement, maxAF);
        }
      }
    }

    // 处理反转
    if (needReverse) {
      isUpTrend = !isUpTrend;
      sar = ep;
      ep = isUpTrend ? current.high : current.low;
      af = initialAF;
    }

    sarValues.push(sar);
    trends.push(isUpTrend ? 'up' : 'down');
    timestamps.push(current.timestamp);
    afHistory.push(af);
  }

  return {
    values: sarValues,
    trend: trends,
    timestamp: timestamps,
    af: afHistory
  };
}

/**
 * 检测SAR信号
 * @param sar SAR结果
 * @param index 当前索引
 * @returns 信号类型
 */
export function detectSARSignal(
  sar: SARResult,
  index: number
): 'buy' | 'sell' | 'hold' {
  if (index < 1) return 'hold';

  const currentTrend = sar.trend[index];
  const previousTrend = sar.trend[index - 1];

  if (currentTrend === 'up' && previousTrend === 'down') {
    return 'buy'; // 上升反转
  } else if (currentTrend === 'down' && previousTrend === 'up') {
    return 'sell'; // 下降反转
  }

  return 'hold';
}

/**
 * 计算SAR止损位
 * @param currentPrice 当前价格
 * @param sarValue SAR值
 * @param trend 趋势方向
 * @returns 止损价格
 */
export function calculateSARStopLoss(
  currentPrice: number,
  sarValue: number,
  trend: 'up' | 'down'
): number {
  if (trend === 'up') {
    // 上升趋势，止损在SAR下方
    return sarValue;
  } else {
    // 下降趋势，止损在SAR上方
    return sarValue;
  }
}

/**
 * SAR指标解读
 * @param price 当前价格
 * @param sarValue SAR值
 * @param trend 趋势
 * @returns 解读结果
 */
export function interpretSAR(
  price: number,
  sarValue: number,
  trend: 'up' | 'down'
): string {
  const distance = Math.abs(price - sarValue);
  const distancePercent = (distance / price) * 100;

  if (trend === 'up') {
    if (distancePercent < 1) {
      return '上升趋势，接近支撑';
    } else if (distancePercent < 3) {
      return '上升趋势，正常距离';
    } else {
      return '上升趋势，距离较远';
    }
  } else {
    if (distancePercent < 1) {
      return '下降趋势，接近阻力';
    } else if (distancePercent < 3) {
      return '下降趋势，正常距离';
    } else {
      return '下降趋势，距离较远';
    }
  }
}

export default {
  calculateSAR,
  detectSARSignal,
  calculateSARStopLoss,
  interpretSAR
};
