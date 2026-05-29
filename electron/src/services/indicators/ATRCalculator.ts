/**
 * ATR (Average True Range) 指标计算器
 * 真实波幅 - 衡量市场波动性
 */

export interface ATRResult {
  values: number[];
  period: number;
  timestamp: number[];
}

export interface OHLCData {
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

/**
 * 计算ATR指标
 * @param data OHLC数据数组
 * @param period 周期，默认14
 * @returns ATR结果
 */
export function calculateATR(
  data: OHLCData[],
  period: number = 14
): ATRResult {
  if (data.length < period + 1) {
    throw new Error(`数据长度至少需要 ${period + 1} 个数据点`);
  }

  const trueRanges: number[] = [];
  const timestamps: number[] = [];

  // 计算真实波幅 (True Range)
  for (let i = 1; i < data.length; i++) {
    const current = data[i];
    const previous = data[i - 1];

    // TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
    const highLow = current.high - current.low;
    const highClose = Math.abs(current.high - previous.close);
    const lowClose = Math.abs(current.low - previous.close);

    const tr = Math.max(highLow, highClose, lowClose);
    trueRanges.push(tr);
    timestamps.push(current.timestamp);
  }

  // 使用EMA计算ATR
  const atrValues = calculateEMA(trueRanges, period);

  return {
    values: atrValues,
    period,
    timestamp: timestamps.slice(period - 1)
  };
}

/**
 * 计算指数移动平均 (EMA)
 * @param data 数据数组
 * @param period 周期
 * @returns EMA值数组
 */
function calculateEMA(data: number[], period: number): number[] {
  const ema: number[] = [];
  const multiplier = 2 / (period + 1);

  // 第一个EMA值使用SMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i];
  }
  let prevEMA = sum / period;
  ema.push(prevEMA);

  // 计算后续EMA值
  for (let i = period; i < data.length; i++) {
    const currentEMA = (data[i] - prevEMA) * multiplier + prevEMA;
    ema.push(currentEMA);
    prevEMA = currentEMA;
  }

  return ema;
}

/**
 * ATR指标解读
 * @param atr ATR值
 * @param price 当前价格
 * @returns 波动性描述
 */
export function interpretATR(atr: number, price: number): string {
  const atrPercent = (atr / price) * 100;

  if (atrPercent < 1) {
    return '低波动';
  } else if (atrPercent < 2) {
    return '正常波动';
  } else if (atrPercent < 3) {
    return '高波动';
  } else {
    return '极高波动';
  }
}

export default {
  calculateATR,
  interpretATR
};
