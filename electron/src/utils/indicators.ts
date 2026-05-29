/**
 * 技术指标计算工具
 *
 * 提供常用技术指标的计算方法：
 * - MA (移动平均线)
 * - EMA (指数移动平均线)
 * - RSI (相对强弱指标)
 * - MACD (指数平滑异同移动平均线)
 * - KDJ (随机指标)
 * - BOLL (布林带)
 */

/**
 * 计算简单移动平均线 (MA)
 * @param data - 价格数据数组
 * @param period - 周期
 * @returns MA值数组
 */
export function calculateMA(data: number[], period: number): number[] {
  if (!data || data.length < period) {
    return [];
  }

  const result: number[] = [];

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(NaN);
      continue;
    }

    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j];
    }
    result.push(sum / period);
  }

  return result;
}

/**
 * 计算指数移动平均线 (EMA)
 * @param data - 价格数据数组
 * @param period - 周期
 * @returns EMA值数组
 */
export function calculateEMA(data: number[], period: number): number[] {
  if (!data || data.length < period) {
    return [];
  }

  const result: number[] = [];
  const multiplier = 2 / (period + 1);

  // 第一个EMA值使用SMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i];
    if (i < period - 1) {
      result.push(NaN);
    }
  }
  result.push(sum / period);

  // 后续EMA值
  for (let i = period; i < data.length; i++) {
    const ema = (data[i] - result[i - 1]) * multiplier + result[i - 1];
    result.push(ema);
  }

  return result;
}

/**
 * 计算相对强弱指标 (RSI)
 * @param data - 价格数据数组
 * @param period - 周期，默认14
 * @returns RSI值数组
 */
export function calculateRSI(data: number[], period: number = 14): number[] {
  if (!data || data.length < period + 1) {
    return [];
  }

  const result: number[] = [];
  const gains: number[] = [];
  const losses: number[] = [];

  // 计算涨跌幅
  for (let i = 1; i < data.length; i++) {
    const change = data[i] - data[i - 1];
    gains.push(change > 0 ? change : 0);
    losses.push(change < 0 ? -change : 0);
  }

  // 计算初始平均涨跌幅
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < period; i++) {
    avgGain += gains[i];
    avgLoss += losses[i];
    result.push(NaN);
  }
  avgGain /= period;
  avgLoss /= period;

  // 计算第一个RSI
  const rs = avgGain / avgLoss;
  result.push(100 - (100 / (1 + rs)));

  // 计算后续RSI
  for (let i = period; i < gains.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;

    const rs = avgGain / avgLoss;
    result.push(100 - (100 / (1 + rs)));
  }

  return result;
}

/**
 * MACD计算结果
 */
export interface MACDResult {
  dif: number[];
  dea: number[];
  macd: number[];
}

/**
 * 计算MACD指标
 * @param data - 价格数据数组
 * @param fastPeriod - 快线周期，默认12
 * @param slowPeriod - 慢线周期，默认26
 * @param signalPeriod - 信号线周期，默认9
 * @returns MACD结果对象
 */
export function calculateMACD(
  data: number[],
  fastPeriod: number = 12,
  slowPeriod: number = 26,
  signalPeriod: number = 9
): MACDResult {
  if (!data || data.length < slowPeriod + signalPeriod) {
    return { dif: [], dea: [], macd: [] };
  }

  // 计算快线和慢线EMA
  const emaFast = calculateEMA(data, fastPeriod);
  const emaSlow = calculateEMA(data, slowPeriod);

  // 计算DIF
  const dif: number[] = [];
  for (let i = 0; i < data.length; i++) {
    if (isNaN(emaFast[i]) || isNaN(emaSlow[i])) {
      dif.push(NaN);
    } else {
      dif.push(emaFast[i] - emaSlow[i]);
    }
  }

  // 计算DEA (DIF的EMA)
  const validDif = dif.filter(v => !isNaN(v));
  const deaValues = calculateEMA(validDif, signalPeriod);

  // 填充DEA数组
  const dea: number[] = [];
  let deaIndex = 0;
  for (let i = 0; i < dif.length; i++) {
    if (isNaN(dif[i])) {
      dea.push(NaN);
    } else {
      dea.push(deaValues[deaIndex++] || NaN);
    }
  }

  // 计算MACD柱
  const macd: number[] = [];
  for (let i = 0; i < data.length; i++) {
    if (isNaN(dif[i]) || isNaN(dea[i])) {
      macd.push(NaN);
    } else {
      macd.push((dif[i] - dea[i]) * 2);
    }
  }

  return { dif, dea, macd };
}

/**
 * KDJ计算结果
 */
export interface KDJResult {
  k: number[];
  d: number[];
  j: number[];
}

/**
 * 计算KDJ指标
 * @param high - 最高价数组
 * @param low - 最低价数组
 * @param close - 收盘价数组
 * @param period - N周期，默认9
 * @param m1 - M1周期，默认3
 * @param m2 - M2周期，默认3
 * @returns KDJ结果对象
 */
export function calculateKDJ(
  high: number[],
  low: number[],
  close: number[],
  period: number = 9,
  m1: number = 3,
  m2: number = 3
): KDJResult {
  if (!high || !low || !close || high.length < period) {
    return { k: [], d: [], j: [] };
  }

  const k: number[] = [];
  const d: number[] = [];
  const j: number[] = [];

  let prevK = 50;
  let prevD = 50;

  for (let i = 0; i < close.length; i++) {
    if (i < period - 1) {
      k.push(NaN);
      d.push(NaN);
      j.push(NaN);
      continue;
    }

    // 计算N日内的最高价和最低价
    let highestHigh = high[i];
    let lowestLow = low[i];
    for (let j = 1; j < period; j++) {
      if (i - j >= 0) {
        highestHigh = Math.max(highestHigh, high[i - j]);
        lowestLow = Math.min(lowestLow, low[i - j]);
      }
    }

    // 计算RSV
    const rsv = highestHigh === lowestLow
      ? 50
      : ((close[i] - lowestLow) / (highestHigh - lowestLow)) * 100;

    // 计算K值
    const kValue = (prevK * (m1 - 1) + rsv) / m1;
    k.push(kValue);

    // 计算D值
    const dValue = (prevD * (m2 - 1) + kValue) / m2;
    d.push(dValue);

    // 计算J值
    const jValue = 3 * kValue - 2 * dValue;
    j.push(jValue);

    prevK = kValue;
    prevD = dValue;
  }

  return { k, d, j };
}

/**
 * 布林带计算结果
 */
export interface BOLLResult {
  upper: number[];
  middle: number[];
  lower: number[];
}

/**
 * 计算布林带 (BOLL)
 * @param data - 价格数据数组
 * @param period - 周期，默认20
 * @param stdDev - 标准差倍数，默认2
 * @returns 布林带结果对象
 */
export function calculateBOLL(
  data: number[],
  period: number = 20,
  stdDev: number = 2
): BOLLResult {
  if (!data || data.length < period) {
    return { upper: [], middle: [], lower: [] };
  }

  const upper: number[] = [];
  const middle: number[] = [];
  const lower: number[] = [];

  // 计算中轨（MA）
  const ma = calculateMA(data, period);

  // 计算上下轨
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1 || isNaN(ma[i])) {
      upper.push(NaN);
      middle.push(NaN);
      lower.push(NaN);
      continue;
    }

    // 计算标准差
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += Math.pow(data[i - j] - ma[i], 2);
    }
    const std = Math.sqrt(sum / period);

    middle.push(ma[i]);
    upper.push(ma[i] + stdDev * std);
    lower.push(ma[i] - stdDev * std);
  }

  return { upper, middle, lower };
}

/**
 * 计算多条MA线
 * @param data - 价格数据数组
 * @param periods - 周期数组，如 [5, 10, 20, 30]
 * @returns MA值对象
 */
export function calculateMultipleMA(
  data: number[],
  periods: number[]
): Record<string, number[]> {
  const result: Record<string, number[]> = {};

  for (const period of periods) {
    result[`MA${period}`] = calculateMA(data, period);
  }

  return result;
}

/**
 * 计算多条EMA线
 * @param data - 价格数据数组
 * @param periods - 周期数组，如 [5, 10, 20, 30]
 * @returns EMA值对象
 */
export function calculateMultipleEMA(
  data: number[],
  periods: number[]
): Record<string, number[]> {
  const result: Record<string, number[]> = {};

  for (const period of periods) {
    result[`EMA${period}`] = calculateEMA(data, period);
  }

  return result;
}

/**
 * 获取最新指标值
 * @param data - 指标数据数组
 * @returns 最新有效值
 */
export function getLatestValue(data: number[]): number | null {
  for (let i = data.length - 1; i >= 0; i--) {
    if (!isNaN(data[i])) {
      return data[i];
    }
  }
  return null;
}

/**
 * 格式化指标值
 * @param value - 指标值
 * @param decimals - 小数位数，默认2
 * @returns 格式化后的字符串
 */
export function formatIndicatorValue(value: number | null, decimals: number = 2): string {
  if (value === null || isNaN(value)) {
    return '--';
  }
  return value.toFixed(decimals);
}
