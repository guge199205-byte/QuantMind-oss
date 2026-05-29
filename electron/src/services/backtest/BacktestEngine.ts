/**
 * 回测引擎
 * 核心回测逻辑，协调各个模块完成回测
 */

import {
  OHLCV,
  Strategy,
  BacktestConfig,
  BacktestResult,
  StrategyContext,
  OrderRequest,
  IndicatorManager
} from '../../types/backtest';
import { OrderSimulator } from './OrderSimulator';
import { PositionManager } from './PositionManager';
import { PerformanceCalculator } from './PerformanceCalculator';
import { IndicatorCalculator } from './IndicatorCalculator';

export class BacktestEngine {
  private orderSimulator: OrderSimulator;
  private positionManager: PositionManager;
  private performanceCalculator: PerformanceCalculator;
  private indicatorCalculator: IndicatorCalculator;

  constructor() {
    this.orderSimulator = new OrderSimulator();
    this.positionManager = new PositionManager(100000);
    this.performanceCalculator = new PerformanceCalculator();
    this.indicatorCalculator = new IndicatorCalculator();
  }

  /**
   * 运行回测
   */
  async run(strategy: Strategy, config: BacktestConfig, data: OHLCV[]): Promise<BacktestResult> {
    const startTime = Date.now();

    // 初始化
    this.orderSimulator = new OrderSimulator(config.commission, config.slippage);
    this.positionManager = new PositionManager(
      config.initialCapital,
      config.leverage || 1,
      config.riskPerTrade || 0.02
    );

    // 准备指标计算器
    this.indicatorCalculator.setData(data);

    // 创建策略上下文
    const context = this.createStrategyContext(data);

    // 调用策略初始化
    if (strategy.initialize) {
      strategy.initialize(context);
    }

    // 遍历每根K线
    for (let i = 0; i < data.length; i++) {
      const bar = data[i];

      // 更新上下文
      context.currentBar = bar;
      context.barIndex = i;
      context.capital = this.positionManager.getCapital();
      context.equity = this.positionManager.getEquity();
      context.position = this.positionManager.getPosition();
      context.bars = data.slice(0, i + 1);

      // 更新持仓价格
      this.positionManager.updatePosition(bar.close);

      // 调用策略逻辑
      strategy.onBar(bar, context);
    }

    // 调用策略结束回调
    if (strategy.finalize) {
      strategy.finalize(context);
    }

    // 如果还有持仓，强制平仓
    const lastBar = data[data.length - 1];
    if (this.positionManager.getPosition()) {
      this.positionManager.closePosition(lastBar.close, lastBar.timestamp);
    }

    // 获取交易记录
    const trades = this.positionManager.getTrades();

    // 构建权益曲线
    const equityCurve = this.performanceCalculator.buildEquityCurve(
      trades,
      config.initialCapital,
      data.map(d => d.timestamp)
    );

    // 计算绩效指标
    const metrics = this.performanceCalculator.calculateMetrics(
      trades,
      equityCurve,
      config.initialCapital,
      config.startDate ? new Date(config.startDate) : undefined,
      config.endDate ? new Date(config.endDate) : undefined
    );

    // 计算回撤分析
    const drawdown = this.performanceCalculator.calculateDrawdown(equityCurve.values);

    const endTime = Date.now();

    return {
      config,
      trades,
      equity: equityCurve,
      metrics,
      drawdown,
      startTime,
      endTime,
      executionTime: endTime - startTime
    };
  }

  /**
   * 创建策略上下文
   */
  private createStrategyContext(data: OHLCV[]): StrategyContext {
    const context: StrategyContext = {
      buy: (size: number, price?: number) => {
        this.executeBuy(size, price, data);
      },
      sell: (size: number, price?: number) => {
        this.executeSell(size, price, data);
      },
      closePosition: () => {
        const currentBar = context.currentBar;
        if (currentBar && this.positionManager.getPosition()) {
          this.positionManager.closePosition(currentBar.close, currentBar.timestamp);
        }
      },
      position: null,
      capital: this.positionManager.getCapital(),
      equity: this.positionManager.getEquity(),
      indicators: this.createIndicatorManager(data),
      bars: [],
      currentBar: data[0],
      barIndex: 0
    };

    return context;
  }

  /**
   * 创建指标管理器
   */
  private createIndicatorManager(data: OHLCV[]): IndicatorManager {
    return {
      sma: (period: number) => this.indicatorCalculator.calculateSMA(data, period),
      ema: (period: number) => this.indicatorCalculator.calculateEMA(data, period),
      rsi: (period: number) => this.indicatorCalculator.calculateRSI(data, period),
      macd: () => this.indicatorCalculator.calculateMACD(data),
      bollinger: (period: number, stdDev: number) =>
        this.indicatorCalculator.calculateBollinger(data, period, stdDev),
      atr: (period: number) => this.indicatorCalculator.calculateATR(data, period),
      obv: () => this.indicatorCalculator.calculateOBV(data)
    };
  }

  /**
   * 执行买入
   */
  private executeBuy(size: number, price: number | undefined, data: OHLCV[]): void {
    const currentBar = data[data.length - 1];

    const order: OrderRequest = {
      type: price ? 'limit' : 'market',
      side: 'buy',
      size,
      price
    };

    let execution;
    if (order.type === 'market') {
      execution = this.orderSimulator.simulateMarketOrder(order, currentBar, currentBar.timestamp);
    } else {
      execution = this.orderSimulator.simulateLimitOrder(order, currentBar, currentBar.timestamp);
    }

    if (execution) {
      this.positionManager.openPosition(
        'SYMBOL',
        'buy',
        size,
        execution
      );
    }
  }

  /**
   * 执行卖出
   */
  private executeSell(size: number, price: number | undefined, data: OHLCV[]): void {
    const currentBar = data[data.length - 1];

    const order: OrderRequest = {
      type: price ? 'limit' : 'market',
      side: 'sell',
      size,
      price
    };

    let execution;
    if (order.type === 'market') {
      execution = this.orderSimulator.simulateMarketOrder(order, currentBar, currentBar.timestamp);
    } else {
      execution = this.orderSimulator.simulateLimitOrder(order, currentBar, currentBar.timestamp);
    }

    if (execution) {
      // 如果有持仓，先平仓
      if (this.positionManager.getPosition()) {
        this.positionManager.closePosition(currentBar.close, currentBar.timestamp);
      }

      // 开空仓
      this.positionManager.openPosition(
        'SYMBOL',
        'sell',
        size,
        execution
      );
    }
  }

  /**
   * 批量回测（用于参数优化）
   */
  async runBatch(
    strategy: Strategy,
    configs: BacktestConfig[],
    data: OHLCV[],
    progressCallback?: (current: number, total: number) => void
  ): Promise<BacktestResult[]> {
    const results: BacktestResult[] = [];

    for (let i = 0; i < configs.length; i++) {
      const result = await this.run(strategy, configs[i], data);
      results.push(result);

      if (progressCallback) {
        progressCallback(i + 1, configs.length);
      }
    }

    return results;
  }

  /**
   * 获取回测统计摘要
   */
  getSummary(result: BacktestResult): string {
    const m = result.metrics;
    return `
回测摘要
========
总收益率: ${(m.totalReturn * 100).toFixed(2)}%
年化收益率: ${(m.annualizedReturn * 100).toFixed(2)}%
夏普比率: ${m.sharpeRatio.toFixed(2)}
最大回撤: ${(m.maxDrawdown * 100).toFixed(2)}%
胜率: ${(m.winRate * 100).toFixed(2)}%
盈亏比: ${m.profitFactor.toFixed(2)}
总交易次数: ${m.totalTrades}
盈利次数: ${m.winningTrades}
亏损次数: ${m.losingTrades}
执行时间: ${result.executionTime}ms
    `.trim();
  }
}
