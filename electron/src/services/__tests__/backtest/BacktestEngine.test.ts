/**
 * 回测引擎测试
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { BacktestEngine } from '../../backtest/BacktestEngine';
import { Strategy, BacktestConfig, OHLCV } from '../../../types/backtest';

describe('BacktestEngine', () => {
  let engine: BacktestEngine;
  let mockData: OHLCV[];
  let config: BacktestConfig;

  beforeEach(() => {
    engine = new BacktestEngine();

    // 生成测试数据
    mockData = generateTestData(100);

    // 测试配置
    config = {
      symbol: 'TEST',
      startDate: new Date('2024-01-01'),
      endDate: new Date('2024-04-01'),
      initialCapital: 100000,
      commission: 0.001,
      slippage: 0.001,
      leverage: 1
    };
  });

  it('应该成功执行简单策略', async () => {
    const strategy: Strategy = {
      name: '测试策略',
      version: '1.0.0',
      parameters: [],
      onBar: (bar, context) => {
        const index = context.barIndex;

        // 简单的买入持有策略
        if (index === 10 && !context.position) {
          context.buy(1);
        }
      }
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result).toBeDefined();
    expect(result.trades.length).toBeGreaterThan(0);
    expect(result.equity.values.length).toBeGreaterThan(0);
    expect(result.metrics).toBeDefined();
  });

  it('应该正确计算双均线策略', async () => {
    const strategy: Strategy = {
      name: '双均线策略',
      version: '1.0.0',
      parameters: [],
      onBar: (bar, context) => {
        const index = context.barIndex;

        if (index < 20) return;

        const sma10 = context.indicators.sma(10);
        const sma20 = context.indicators.sma(20);

        if (sma10[index] > sma20[index] && !context.position) {
          context.buy(1);
        } else if (sma10[index] < sma20[index] && context.position) {
          context.closePosition();
        }
      }
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result.trades.length).toBeGreaterThan(0);
    expect(result.metrics.totalTrades).toBeGreaterThan(0);
  });

  it('应该正确处理手续费和滑点', async () => {
    const strategy: Strategy = {
      name: '费用测试策略',
      version: '1.0.0',
      parameters: [],
      onBar: (bar, context) => {
        if (context.barIndex === 10) {
          context.buy(100);
        }
        if (context.barIndex === 20) {
          context.closePosition();
        }
      }
    };

    const result = await engine.run(strategy, config, mockData);

    // 验证有手续费和滑点记录
    const totalCommission = result.trades.reduce((sum, t) => sum + t.commission, 0);
    const totalSlippage = result.trades.reduce((sum, t) => sum + t.slippage, 0);

    expect(totalCommission).toBeGreaterThan(0);
    expect(totalSlippage).toBeGreaterThan(0);
  });

  it('应该正确计算绩效指标', async () => {
    const strategy: Strategy = {
      name: '绩效测试策略',
      version: '1.0.0',
      parameters: [],
      onBar: (bar, context) => {
        if (context.barIndex === 10) {
          context.buy(100);
        }
        if (context.barIndex === 50) {
          context.closePosition();
        }
      }
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result.metrics.totalReturn).toBeDefined();
    expect(result.metrics.annualizedReturn).toBeDefined();
    expect(result.metrics.sharpeRatio).toBeDefined();
    expect(result.metrics.maxDrawdown).toBeDefined();
    expect(result.metrics.winRate).toBeDefined();
  });

  it('应该生成正确的权益曲线', async () => {
    const strategy: Strategy = {
      name: '权益曲线测试',
      version: '1.0.0',
      parameters: [],
      onBar: (bar, context) => {
        if (context.barIndex === 10) {
          context.buy(100);
        }
        if (context.barIndex === 30) {
          context.closePosition();
        }
      }
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result.equity.timestamps.length).toBeGreaterThan(0);
    expect(result.equity.values.length).toBeGreaterThan(0);
    expect(result.equity.returns.length).toBeGreaterThan(0);
    expect(result.equity.drawdowns.length).toBeGreaterThan(0);

    // 第一个权益值应该是初始资金
    expect(result.equity.values[0]).toBe(config.initialCapital);
  });

  it('应该返回执行时间', async () => {
    const strategy: Strategy = {
      name: '执行时间测试',
      version: '1.0.0',
      parameters: [],
      onBar: () => {}
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result.executionTime).toBeGreaterThanOrEqual(0);
    expect(result.startTime).toBeLessThanOrEqual(result.endTime);
  });

  it('应该正确处理空策略', async () => {
    const strategy: Strategy = {
      name: '空策略',
      version: '1.0.0',
      parameters: [],
      onBar: () => {
        // 什么都不做
      }
    };

    const result = await engine.run(strategy, config, mockData);

    expect(result.trades.length).toBe(0);
    expect(result.metrics.totalTrades).toBe(0);
    expect(result.equity.values[result.equity.values.length - 1]).toBe(config.initialCapital);
  });

  it('应该调用策略的initialize和finalize方法', async () => {
    let initCalled = false;
    let finalizeCalled = false;

    const strategy: Strategy = {
      name: '生命周期测试',
      version: '1.0.0',
      parameters: [],
      initialize: () => {
        initCalled = true;
      },
      onBar: () => {},
      finalize: () => {
        finalizeCalled = true;
      }
    };

    await engine.run(strategy, config, mockData);

    expect(initCalled).toBe(true);
    expect(finalizeCalled).toBe(true);
  });
});

// 生成测试数据
function generateTestData(count: number): OHLCV[] {
  const data: OHLCV[] = [];
  let price = 100;
  const startTime = new Date('2024-01-01').getTime();

  for (let i = 0; i < count; i++) {
    price = price + (Math.random() - 0.5) * 2;
    const open = price;
    const high = price + Math.random();
    const low = price - Math.random();
    const close = low + Math.random() * (high - low);

    data.push({
      timestamp: startTime + i * 24 * 60 * 60 * 1000,
      open,
      high,
      low,
      close,
      volume: Math.random() * 1000000
    });
  }

  return data;
}
