/**
 * 技术指标计算器测试
 */

import { describe, it, expect } from 'vitest';
import { calculateATR } from '../ATRCalculator';
import { calculateOBV } from '../OBVCalculator';
import { calculateSAR } from '../SARCalculator';
import { calculateCCI } from '../CCICalculator';
import { calculateWR } from '../WRCalculator';

// 测试数据
const testData = [
  { high: 110, low: 100, close: 105, volume: 1000, timestamp: 1 },
  { high: 115, low: 105, close: 112, volume: 1200, timestamp: 2 },
  { high: 120, low: 110, close: 115, volume: 1500, timestamp: 3 },
  { high: 118, low: 112, close: 114, volume: 1300, timestamp: 4 },
  { high: 125, low: 115, close: 122, volume: 1800, timestamp: 5 },
  { high: 128, low: 120, close: 125, volume: 2000, timestamp: 6 },
  { high: 130, low: 122, close: 127, volume: 2200, timestamp: 7 },
  { high: 132, low: 125, close: 129, volume: 2100, timestamp: 8 },
  { high: 135, low: 128, close: 133, volume: 2500, timestamp: 9 },
  { high: 138, low: 130, close: 135, volume: 2800, timestamp: 10 },
  { high: 140, low: 132, close: 137, volume: 3000, timestamp: 11 },
  { high: 142, low: 135, close: 139, volume: 3200, timestamp: 12 },
  { high: 145, low: 137, close: 142, volume: 3500, timestamp: 13 },
  { high: 148, low: 140, close: 145, volume: 3800, timestamp: 14 },
  { high: 150, low: 142, close: 147, volume: 4000, timestamp: 15 },
];

describe('ATR Calculator', () => {
  it('应该正确计算ATR', () => {
    const result = calculateATR(testData, 5);

    expect(result.values).toBeDefined();
    expect(result.values.length).toBeGreaterThan(0);
    expect(result.period).toBe(5);
    expect(result.values.every(v => v > 0)).toBe(true);
  });

  it('数据不足时应该抛出错误', () => {
    const shortData = testData.slice(0, 3);
    expect(() => calculateATR(shortData, 5)).toThrow();
  });

  it('ATR值应该随波动性变化', () => {
    const result = calculateATR(testData, 5);
    expect(result.values[0]).toBeGreaterThan(0);
  });
});

describe('OBV Calculator', () => {
  it('应该正确计算OBV', () => {
    const result = calculateOBV(testData);

    expect(result.values).toBeDefined();
    expect(result.values.length).toBe(testData.length);
    expect(result.timestamp.length).toBe(testData.length);
  });

  it('价格上涨时OBV应该增加', () => {
    const result = calculateOBV(testData);
    // 前几天都是上涨的，OBV应该递增
    expect(result.values[5]).toBeGreaterThan(result.values[0]);
  });

  it('数据不足时应该抛出错误', () => {
    const shortData = testData.slice(0, 1);
    expect(() => calculateOBV(shortData)).toThrow();
  });
});

describe('SAR Calculator', () => {
  it('应该正确计算SAR', () => {
    const result = calculateSAR(testData);

    expect(result.values).toBeDefined();
    expect(result.values.length).toBe(testData.length);
    expect(result.trend).toBeDefined();
    expect(result.trend.length).toBe(testData.length);
  });

  it('应该识别趋势方向', () => {
    const result = calculateSAR(testData);

    // 趋势应该是'up'或'down'
    expect(['up', 'down'].includes(result.trend[0])).toBe(true);
  });

  it('加速因子应该在合理范围内', () => {
    const result = calculateSAR(testData, 0.02, 0.2);

    expect(result.af.every(af => af >= 0.02 && af <= 0.2)).toBe(true);
  });

  it('数据不足时应该抛出错误', () => {
    const shortData = testData.slice(0, 2);
    expect(() => calculateSAR(shortData)).toThrow();
  });
});

describe('CCI Calculator', () => {
  it('应该正确计算CCI', () => {
    const result = calculateCCI(testData, 5);

    expect(result.values).toBeDefined();
    expect(result.values.length).toBeGreaterThan(0);
    expect(result.period).toBe(5);
  });

  it('CCI值应该在合理范围内', () => {
    const result = calculateCCI(testData, 5);

    // CCI通常在-200到+200之间
    expect(result.values.every(v => v > -300 && v < 300)).toBe(true);
  });

  it('应该包含超买超卖线', () => {
    const result = calculateCCI(testData, 5);

    expect(result.overbought).toBeDefined();
    expect(result.oversold).toBeDefined();
    expect(result.overbought[0]).toBe(100);
    expect(result.oversold[0]).toBe(-100);
  });

  it('数据不足时应该抛出错误', () => {
    const shortData = testData.slice(0, 3);
    expect(() => calculateCCI(shortData, 5)).toThrow();
  });
});

describe('WR Calculator', () => {
  it('应该正确计算WR', () => {
    const result = calculateWR(testData, 5);

    expect(result.values).toBeDefined();
    expect(result.values.length).toBeGreaterThan(0);
    expect(result.period).toBe(5);
  });

  it('WR值应该在-100到0之间', () => {
    const result = calculateWR(testData, 5);

    expect(result.values.every(v => v >= -100 && v <= 0)).toBe(true);
  });

  it('应该包含超买超卖线', () => {
    const result = calculateWR(testData, 5);

    expect(result.overbought).toBeDefined();
    expect(result.oversold).toBeDefined();
    expect(result.overbought[0]).toBe(-20);
    expect(result.oversold[0]).toBe(-80);
  });

  it('数据不足时应该抛出错误', () => {
    const shortData = testData.slice(0, 3);
    expect(() => calculateWR(shortData, 5)).toThrow();
  });
});

describe('指标集成测试', () => {
  it('应该能同时计算多个指标', () => {
    const atr = calculateATR(testData, 5);
    const obv = calculateOBV(testData);
    const sar = calculateSAR(testData);
    const cci = calculateCCI(testData, 5);
    const wr = calculateWR(testData, 5);

    expect(atr.values.length).toBeGreaterThan(0);
    expect(obv.values.length).toBe(testData.length);
    expect(sar.values.length).toBe(testData.length);
    expect(cci.values.length).toBeGreaterThan(0);
    expect(wr.values.length).toBeGreaterThan(0);
  });

  it('所有指标应该返回时间戳', () => {
    const atr = calculateATR(testData, 5);
    const obv = calculateOBV(testData);
    const sar = calculateSAR(testData);
    const cci = calculateCCI(testData, 5);
    const wr = calculateWR(testData, 5);

    expect(atr.timestamp.length).toBe(atr.values.length);
    expect(obv.timestamp.length).toBe(obv.values.length);
    expect(sar.timestamp.length).toBe(sar.values.length);
    expect(cci.timestamp.length).toBe(cci.values.length);
    expect(wr.timestamp.length).toBe(wr.values.length);
  });
});
