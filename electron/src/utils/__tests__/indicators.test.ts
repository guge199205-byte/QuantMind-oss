/**
 * 技术指标计算工具测试
 */

import { describe, it, expect } from 'vitest';
import {
  calculateMA,
  calculateEMA,
  calculateRSI,
  calculateMACD,
  calculateKDJ,
  calculateBOLL,
  calculateMultipleMA,
  calculateMultipleEMA,
  getLatestValue,
  formatIndicatorValue,
} from '../indicators';

describe('indicators', () => {
  // 测试数据
  const testPrices = [10, 11, 12, 11, 10, 11, 12, 13, 12, 11, 10, 11, 12, 13, 14];
  const testHigh = [11, 12, 13, 12, 11, 12, 13, 14, 13, 12, 11, 12, 13, 14, 15];
  const testLow = [9, 10, 11, 10, 9, 10, 11, 12, 11, 10, 9, 10, 11, 12, 13];

  describe('calculateMA', () => {
    it('应该正确计算MA', () => {
      const ma5 = calculateMA(testPrices, 5);
      expect(ma5).toHaveLength(testPrices.length);
      expect(isNaN(ma5[0])).toBe(true);
      expect(isNaN(ma5[3])).toBe(true);
      expect(isNaN(ma5[4])).toBe(false);
      expect(ma5[4]).toBeCloseTo(10.8, 1);
    });

    it('应该处理空数组', () => {
      const result = calculateMA([], 5);
      expect(result).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateMA([1, 2, 3], 5);
      expect(result).toEqual([]);
    });
  });

  describe('calculateEMA', () => {
    it('应该正确计算EMA', () => {
      const ema5 = calculateEMA(testPrices, 5);
      expect(ema5).toHaveLength(testPrices.length);
      expect(isNaN(ema5[0])).toBe(true);
      expect(isNaN(ema5[4])).toBe(false);
      expect(ema5[4]).toBeGreaterThan(0);
    });

    it('应该处理空数组', () => {
      const result = calculateEMA([], 5);
      expect(result).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateEMA([1, 2, 3], 5);
      expect(result).toEqual([]);
    });
  });

  describe('calculateRSI', () => {
    it('应该正确计算RSI', () => {
      const rsi = calculateRSI(testPrices, 14);
      expect(rsi).toHaveLength(testPrices.length);
      expect(isNaN(rsi[0])).toBe(true);

      const lastRSI = rsi[rsi.length - 1];
      expect(lastRSI).toBeGreaterThan(0);
      expect(lastRSI).toBeLessThan(100);
    });

    it('应该使用默认周期14', () => {
      const rsi = calculateRSI(testPrices);
      expect(rsi).toHaveLength(testPrices.length);
    });

    it('应该处理空数组', () => {
      const result = calculateRSI([]);
      expect(result).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateRSI([1, 2, 3], 14);
      expect(result).toEqual([]);
    });
  });

  describe('calculateMACD', () => {
    it('应该正确计算MACD', () => {
      const prices = Array.from({ length: 50 }, (_, i) => 10 + Math.sin(i / 5) * 2);
      const macd = calculateMACD(prices);

      expect(macd.dif).toHaveLength(prices.length);
      expect(macd.dea).toHaveLength(prices.length);
      expect(macd.macd).toHaveLength(prices.length);
    });

    it('应该使用自定义参数', () => {
      const prices = Array.from({ length: 50 }, (_, i) => 10 + Math.sin(i / 5) * 2);
      const macd = calculateMACD(prices, 8, 17, 7);

      expect(macd.dif).toHaveLength(prices.length);
      expect(macd.dea).toHaveLength(prices.length);
      expect(macd.macd).toHaveLength(prices.length);
    });

    it('应该处理空数组', () => {
      const result = calculateMACD([]);
      expect(result.dif).toEqual([]);
      expect(result.dea).toEqual([]);
      expect(result.macd).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateMACD([1, 2, 3, 4, 5]);
      expect(result.dif).toEqual([]);
      expect(result.dea).toEqual([]);
      expect(result.macd).toEqual([]);
    });
  });

  describe('calculateKDJ', () => {
    it('应该正确计算KDJ', () => {
      const kdj = calculateKDJ(testHigh, testLow, testPrices);

      expect(kdj.k).toHaveLength(testPrices.length);
      expect(kdj.d).toHaveLength(testPrices.length);
      expect(kdj.j).toHaveLength(testPrices.length);
    });

    it('应该使用自定义参数', () => {
      const kdj = calculateKDJ(testHigh, testLow, testPrices, 5, 2, 2);

      expect(kdj.k).toHaveLength(testPrices.length);
      expect(kdj.d).toHaveLength(testPrices.length);
      expect(kdj.j).toHaveLength(testPrices.length);
    });

    it('应该处理空数组', () => {
      const result = calculateKDJ([], [], []);
      expect(result.k).toEqual([]);
      expect(result.d).toEqual([]);
      expect(result.j).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateKDJ([1, 2], [0.5, 1.5], [0.8, 1.8]);
      expect(result.k).toEqual([]);
      expect(result.d).toEqual([]);
      expect(result.j).toEqual([]);
    });

    it('KDJ值应该在合理范围内', () => {
      const kdj = calculateKDJ(testHigh, testLow, testPrices);

      const validK = kdj.k.filter(v => !isNaN(v));
      const validD = kdj.d.filter(v => !isNaN(v));
      const validJ = kdj.j.filter(v => !isNaN(v));

      expect(validK.length).toBeGreaterThan(0);
      expect(validD.length).toBeGreaterThan(0);
      expect(validJ.length).toBeGreaterThan(0);
    });
  });

  describe('calculateBOLL', () => {
    it('应该正确计算布林带', () => {
      const prices = Array.from({ length: 30 }, (_, i) => 10 + Math.sin(i / 5) * 2);
      const boll = calculateBOLL(prices);

      expect(boll.upper).toHaveLength(prices.length);
      expect(boll.middle).toHaveLength(prices.length);
      expect(boll.lower).toHaveLength(prices.length);
    });

    it('应该使用自定义参数', () => {
      const prices = Array.from({ length: 30 }, (_, i) => 10 + Math.sin(i / 5) * 2);
      const boll = calculateBOLL(prices, 10, 1.5);

      expect(boll.upper).toHaveLength(prices.length);
      expect(boll.middle).toHaveLength(prices.length);
      expect(boll.lower).toHaveLength(prices.length);
    });

    it('上轨应该大于中轨，中轨应该大于下轨', () => {
      const prices = Array.from({ length: 30 }, (_, i) => 10 + Math.sin(i / 5) * 2);
      const boll = calculateBOLL(prices);

      for (let i = 20; i < prices.length; i++) {
        if (!isNaN(boll.upper[i]) && !isNaN(boll.middle[i]) && !isNaN(boll.lower[i])) {
          expect(boll.upper[i]).toBeGreaterThan(boll.middle[i]);
          expect(boll.middle[i]).toBeGreaterThan(boll.lower[i]);
        }
      }
    });

    it('应该处理空数组', () => {
      const result = calculateBOLL([]);
      expect(result.upper).toEqual([]);
      expect(result.middle).toEqual([]);
      expect(result.lower).toEqual([]);
    });

    it('应该处理数据不足的情况', () => {
      const result = calculateBOLL([1, 2, 3, 4, 5]);
      expect(result.upper).toEqual([]);
      expect(result.middle).toEqual([]);
      expect(result.lower).toEqual([]);
    });
  });

  describe('calculateMultipleMA', () => {
    it('应该计算多条MA线', () => {
      const periods = [5, 10, 20];
      const result = calculateMultipleMA(testPrices, periods);

      expect(result).toHaveProperty('MA5');
      expect(result).toHaveProperty('MA10');
      expect(result).toHaveProperty('MA20');

      expect(result.MA5).toHaveLength(testPrices.length);
      expect(result.MA10).toHaveLength(testPrices.length);
    });

    it('应该处理空周期数组', () => {
      const result = calculateMultipleMA(testPrices, []);
      expect(Object.keys(result)).toHaveLength(0);
    });
  });

  describe('calculateMultipleEMA', () => {
    it('应该计算多条EMA线', () => {
      const periods = [5, 10, 20];
      const result = calculateMultipleEMA(testPrices, periods);

      expect(result).toHaveProperty('EMA5');
      expect(result).toHaveProperty('EMA10');
      expect(result).toHaveProperty('EMA20');

      expect(result.EMA5).toHaveLength(testPrices.length);
      expect(result.EMA10).toHaveLength(testPrices.length);
    });

    it('应该处理空周期数组', () => {
      const result = calculateMultipleEMA(testPrices, []);
      expect(Object.keys(result)).toHaveLength(0);
    });
  });

  describe('getLatestValue', () => {
    it('应该返回最新有效值', () => {
      const data = [NaN, 1, 2, 3, NaN];
      const result = getLatestValue(data);
      expect(result).toBe(3);
    });

    it('应该返回最后一个有效值', () => {
      const data = [1, 2, 3, 4, 5];
      const result = getLatestValue(data);
      expect(result).toBe(5);
    });

    it('应该处理全是NaN的情况', () => {
      const data = [NaN, NaN, NaN];
      const result = getLatestValue(data);
      expect(result).toBeNull();
    });

    it('应该处理空数组', () => {
      const result = getLatestValue([]);
      expect(result).toBeNull();
    });
  });

  describe('formatIndicatorValue', () => {
    it('应该格式化数值', () => {
      expect(formatIndicatorValue(123.456)).toBe('123.46');
      expect(formatIndicatorValue(123.456, 1)).toBe('123.5');
      expect(formatIndicatorValue(123.456, 3)).toBe('123.456');
    });

    it('应该处理null值', () => {
      expect(formatIndicatorValue(null)).toBe('--');
    });

    it('应该处理NaN值', () => {
      expect(formatIndicatorValue(NaN)).toBe('--');
    });

    it('应该处理0值', () => {
      expect(formatIndicatorValue(0)).toBe('0.00');
    });

    it('应该处理负数', () => {
      expect(formatIndicatorValue(-123.456)).toBe('-123.46');
    });
  });
});
