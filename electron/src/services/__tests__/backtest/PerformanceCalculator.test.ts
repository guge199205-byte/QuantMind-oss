/**
 * 绩效计算器测试
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { PerformanceCalculator } from '../../backtest/PerformanceCalculator';
import { Trade, EquityCurve } from '../../../types/backtest';

describe('PerformanceCalculator', () => {
  let calculator: PerformanceCalculator;

  beforeEach(() => {
    calculator = new PerformanceCalculator();
  });

  describe('calculateDrawdown', () => {
    it('应该正确计算最大回撤', () => {
      const equityValues = [100000, 110000, 105000, 120000, 100000, 115000];

      const result = calculator.calculateDrawdown(equityValues);

      expect(result.maxDrawdown).toBeGreaterThan(0);
      expect(result.drawdownPeriods.length).toBeGreaterThan(0);
    });

    it('应该在没有回撤时返回0', () => {
      const equityValues = [100000, 110000, 120000, 130000, 140000];

      const result = calculator.calculateDrawdown(equityValues);

      expect(result.maxDrawdown).toBe(0);
      expect(result.drawdownPeriods.length).toBe(0);
    });

    it('应该正确识别回撤期', () => {
      const equityValues = [100000, 110000, 90000, 95000, 110000, 100000];

      const result = calculator.calculateDrawdown(equityValues);

      expect(result.drawdownPeriods.length).toBeGreaterThanOrEqual(1);

      const period = result.drawdownPeriods[0];
      expect(period.peak).toBeGreaterThan(period.trough);
      expect(period.duration).toBeGreaterThan(0);
    });
  });

  describe('buildEquityCurve', () => {
    it('应该正确构建权益曲线', () => {
      const trades: Trade[] = [
        {
          id: '1',
          timestamp: 1000,
          symbol: 'TEST',
          side: 'buy',
          price: 100,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: 500
        },
        {
          id: '2',
          timestamp: 2000,
          symbol: 'TEST',
          side: 'sell',
          price: 105,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: -200
        }
      ];

      const initialCapital = 100000;
      const timestamps = [0, 1000, 2000];

      const curve = calculator.buildEquityCurve(trades, initialCapital, timestamps);

      expect(curve.values[0]).toBe(initialCapital);
      expect(curve.values.length).toBeGreaterThan(1);
      expect(curve.timestamps.length).toBe(curve.values.length);
      expect(curve.returns.length).toBe(curve.values.length);
    });

    it('应该正确计算累计盈亏', () => {
      const trades: Trade[] = [
        {
          id: '1',
          timestamp: 1000,
          symbol: 'TEST',
          side: 'buy',
          price: 100,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: 1000
        },
        {
          id: '2',
          timestamp: 2000,
          symbol: 'TEST',
          side: 'sell',
          price: 105,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: 500
        }
      ];

      const curve = calculator.buildEquityCurve(trades, 100000, [0, 1000, 2000]);

      // 权益应该累加
      expect(curve.values[1]).toBe(100000 + 1000);
      expect(curve.values[2]).toBe(100000 + 1000 + 500);
    });
  });

  describe('calculateMetrics', () => {
    it('应该计算完整的绩效指标', () => {
      const trades: Trade[] = [
        {
          id: '1',
          timestamp: 1000,
          symbol: 'TEST',
          side: 'buy',
          price: 100,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: 1000
        },
        {
          id: '2',
          timestamp: 2000,
          symbol: 'TEST',
          side: 'sell',
          price: 105,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: -500
        },
        {
          id: '3',
          timestamp: 3000,
          symbol: 'TEST',
          side: 'buy',
          price: 110,
          size: 100,
          commission: 10,
          slippage: 5,
          pnl: 800
        }
      ];

      const equityCurve: EquityCurve = {
        timestamps: [0, 1000, 2000, 3000],
        values: [100000, 101000, 100500, 101300],
        returns: [0, 0.01, -0.00495, 0.00794],
        drawdowns: [0, 0, 0.00495, 0]
      };

      const metrics = calculator.calculateMetrics(
        trades,
        equityCurve,
        100000,
        new Date('2024-01-01'),
        new Date('2024-12-31')
      );

      expect(metrics.totalTrades).toBe(3);
      expect(metrics.winningTrades).toBe(2);
      expect(metrics.losingTrades).toBe(1);
      expect(metrics.winRate).toBeCloseTo(2/3, 2);
      expect(metrics.totalReturn).toBeCloseTo(0.013, 3);
      expect(metrics.sharpeRatio).toBeDefined();
      expect(metrics.maxDrawdown).toBeDefined();
    });

    it('应该正确计算胜率', () => {
      const trades: Trade[] = [
        { id: '1', timestamp: 1000, symbol: 'TEST', side: 'buy', price: 100, size: 100, commission: 0, slippage: 0, pnl: 100 },
        { id: '2', timestamp: 2000, symbol: 'TEST', side: 'sell', price: 100, size: 100, commission: 0, slippage: 0, pnl: 200 },
        { id: '3', timestamp: 3000, symbol: 'TEST', side: 'buy', price: 100, size: 100, commission: 0, slippage: 0, pnl: -50 },
      ];

      const equityCurve: EquityCurve = {
        timestamps: [0, 1000, 2000, 3000],
        values: [100000, 100100, 100300, 100250],
        returns: [0, 0.001, 0.002, -0.0005],
        drawdowns: [0, 0, 0, 0.0005]
      };

      const metrics = calculator.calculateMetrics(
        trades,
        equityCurve,
        100000,
        new Date('2024-01-01'),
        new Date('2024-12-31')
      );

      expect(metrics.winRate).toBeCloseTo(2/3, 2);
      expect(metrics.averageWin).toBeCloseTo(150, 1);
      expect(metrics.averageLoss).toBeCloseTo(-50, 1);
    });
  });

  describe('calculateSortinoRatio', () => {
    it('应该计算索提诺比率', () => {
      const returns = [0.01, 0.02, -0.01, 0.03, -0.02, 0.015];

      const ratio = calculator.calculateSortinoRatio(returns);

      expect(ratio).toBeDefined();
      expect(typeof ratio).toBe('number');
    });

    it('应该在没有下行风险时返回0', () => {
      const returns = [0.01, 0.02, 0.03, 0.01];

      const ratio = calculator.calculateSortinoRatio(returns);

      expect(ratio).toBe(0);
    });
  });

  describe('calculateCalmarRatio', () => {
    it('应该计算卡玛比率', () => {
      const annualizedReturn = 0.15;
      const maxDrawdown = 0.10;

      const ratio = calculator.calculateCalmarRatio(annualizedReturn, maxDrawdown);

      expect(ratio).toBeCloseTo(1.5, 10);
    });

    it('应该在最大回撤为0时返回0', () => {
      const ratio = calculator.calculateCalmarRatio(0.15, 0);

      expect(ratio).toBe(0);
    });
  });
});
