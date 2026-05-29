/**
 * 指标计算器
 * 为策略提供技术指标计算
 */

import { OHLCV } from '../../types/backtest';

export class IndicatorCalculator {
  private data: OHLCV[] = [];

  setData(data: OHLCV[]): void {
    this.data = data;
  }

  /**
   * 计算简单移动平均线 (SMA)
   */
  calculateSMA(data: OHLCV[], period: number): number[] {
    const result: number[] = [];

    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(NaN);
        continue;
      }

      const sum = data
        .slice(i - period + 1, i + 1)
        .reduce((acc, bar) => acc + bar.close, 0);

      result.push(sum / period);
    }

    return result;
  }

  /**
   * 计算指数移动平均线 (EMA)
   */
  calculateEMA(data: OHLCV[], period: number): number[] {
    const result: number[] = [];
    const multiplier = 2 / (period + 1);

    // 第一个值使用SMA
    let ema = data.slice(0, period).reduce((sum, bar) => sum + bar.close, 0) / period;

    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(NaN);
        continue;
      }

      if (i === period - 1) {
        result.push(ema);
      } else {
        ema = (data[i].close - ema) * multiplier + ema;
        result.push(ema);
      }
    }

    return result;
  }

  /**
   * 计算相对强弱指标 (RSI)
   */
  calculateRSI(data: OHLCV[], period: number = 14): number[] {
    const result: number[] = [];
    const changes: number[] = [];

    // 计算价格变化
    for (let i = 1; i < data.length; i++) {
      changes.push(data[i].close - data[i - 1].close);
    }

    for (let i = 0; i < data.length; i++) {
      if (i < period) {
        result.push(NaN);
        continue;
      }

      const relevantChanges = changes.slice(i - period, i);
      const gains = relevantChanges.filter(c => c > 0).reduce((sum, c) => sum + c, 0);
      const losses = Math.abs(relevantChanges.filter(c => c < 0).reduce((sum, c) => sum + c, 0));

      const avgGain = gains / period;
      const avgLoss = losses / period;

      if (avgLoss === 0) {
        result.push(100);
      } else {
        const rs = avgGain / avgLoss;
        const rsi = 100 - (100 / (1 + rs));
        result.push(rsi);
      }
    }

    return result;
  }

  /**
   * 计算MACD
   */
  calculateMACD(
    data: OHLCV[],
    fastPeriod: number = 12,
    slowPeriod: number = 26,
    signalPeriod: number = 9
  ): { macd: number[]; signal: number[]; histogram: number[] } {
    const fastEMA = this.calculateEMA(data, fastPeriod);
    const slowEMA = this.calculateEMA(data, slowPeriod);

    // 计算MACD线
    const macd: number[] = fastEMA.map((fast, i) => fast - slowEMA[i]);

    // 计算信号线 (MACD的EMA)
    const validMacd = macd.filter(v => !isNaN(v));
    const macdData: OHLCV[] = validMacd.map((value, i) => {
      const src = data[i + slowPeriod - 1];
      return {
        date: src?.date || (src?.timestamp ? new Date(src.timestamp).toISOString() : ''),
        timestamp: src?.timestamp,
        open: value,
        high: value,
        low: value,
        close: value,
        volume: 0
      } as OHLCV;
    });

    const signalEMA = this.calculateEMA(macdData, signalPeriod);

    // 补齐信号线数组长度
    const signal: number[] = new Array(slowPeriod - 1).fill(NaN).concat(signalEMA);

    // 计算柱状图
    const histogram: number[] = macd.map((m, i) => m - signal[i]);

    return { macd, signal, histogram };
  }

  /**
   * 计算布林带 (Bollinger Bands)
   */
  calculateBollinger(
    data: OHLCV[],
    period: number = 20,
    stdDev: number = 2
  ): { upper: number[]; middle: number[]; lower: number[] } {
    const middle = this.calculateSMA(data, period);
    const upper: number[] = [];
    const lower: number[] = [];

    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        upper.push(NaN);
        lower.push(NaN);
        continue;
      }

      const slice = data.slice(i - period + 1, i + 1);
      const mean = middle[i];
      const variance = slice.reduce((sum, bar) => sum + Math.pow(bar.close - mean, 2), 0) / period;
      const sd = Math.sqrt(variance);

      upper.push(mean + stdDev * sd);
      lower.push(mean - stdDev * sd);
    }

    return { upper, middle, lower };
  }

  /**
   * 计算ATR (Average True Range)
   */
  calculateATR(data: OHLCV[], period: number = 14): number[] {
    const result: number[] = [];
    const trueRanges: number[] = [];

    // 计算真实波幅
    for (let i = 0; i < data.length; i++) {
      if (i === 0) {
        trueRanges.push(data[i].high - data[i].low);
      } else {
        const tr = Math.max(
          data[i].high - data[i].low,
          Math.abs(data[i].high - data[i - 1].close),
          Math.abs(data[i].low - data[i - 1].close)
        );
        trueRanges.push(tr);
      }
    }

    // 计算ATR (使用RMA - Wilder's smoothing)
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(NaN);
        continue;
      }

      if (i === period - 1) {
        // 第一个ATR值是简单平均
        const sum = trueRanges.slice(0, period).reduce((a, b) => a + b, 0);
        result.push(sum / period);
      } else {
        // 后续使用Wilder's smoothing
        const prevATR = result[i - 1];
        const atr = (prevATR * (period - 1) + trueRanges[i]) / period;
        result.push(atr);
      }
    }

    return result;
  }

  /**
   * 计算OBV (On Balance Volume)
   */
  calculateOBV(data: OHLCV[]): number[] {
    const result: number[] = [0];

    for (let i = 1; i < data.length; i++) {
      const prevOBV = result[i - 1];

      if (data[i].close > data[i - 1].close) {
        result.push(prevOBV + data[i].volume);
      } else if (data[i].close < data[i - 1].close) {
        result.push(prevOBV - data[i].volume);
      } else {
        result.push(prevOBV);
      }
    }

    return result;
  }

  /**
   * 计算SAR (Parabolic SAR)
   */
  calculateSAR(
    data: OHLCV[],
    acceleration: number = 0.02,
    maxAcceleration: number = 0.2
  ): number[] {
    const result: number[] = [];

    if (data.length < 2) {
      return result;
    }

    let isUptrend = data[1].close > data[0].close;
    let sar = isUptrend ? data[0].low : data[0].high;
    let ep = isUptrend ? data[0].high : data[0].low;
    let af = acceleration;

    result.push(sar);

    for (let i = 1; i < data.length; i++) {
      // 更新SAR
      sar = sar + af * (ep - sar);

      // 确保SAR不在当前K线范围内
      if (isUptrend) {
        sar = Math.min(sar, data[i - 1].low, i > 1 ? data[i - 2].low : data[i - 1].low);
      } else {
        sar = Math.max(sar, data[i - 1].high, i > 1 ? data[i - 2].high : data[i - 1].high);
      }

      // 检查是否反转
      if ((isUptrend && data[i].low < sar) || (!isUptrend && data[i].high > sar)) {
        isUptrend = !isUptrend;
        sar = ep;
        ep = isUptrend ? data[i].high : data[i].low;
        af = acceleration;
      } else {
        // 更新极值点和加速因子
        if (isUptrend && data[i].high > ep) {
          ep = data[i].high;
          af = Math.min(af + acceleration, maxAcceleration);
        } else if (!isUptrend && data[i].low < ep) {
          ep = data[i].low;
          af = Math.min(af + acceleration, maxAcceleration);
        }
      }

      result.push(sar);
    }

    return result;
  }

  /**
   * 计算CCI (Commodity Channel Index)
   */
  calculateCCI(data: OHLCV[], period: number = 20): number[] {
    const result: number[] = [];
    const constant = 0.015;

    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(NaN);
        continue;
      }

      const slice = data.slice(i - period + 1, i + 1);

      // 计算典型价格
      const typicalPrices = slice.map(bar => (bar.high + bar.low + bar.close) / 3);

      // 计算简单移动平均
      const sma = typicalPrices.reduce((sum, tp) => sum + tp, 0) / period;

      // 计算平均偏差
      const meanDeviation = typicalPrices.reduce((sum, tp) => sum + Math.abs(tp - sma), 0) / period;

      // 计算CCI
      const currentTP = typicalPrices[typicalPrices.length - 1];
      const cci = (currentTP - sma) / (constant * meanDeviation);

      result.push(cci);
    }

    return result;
  }
}
