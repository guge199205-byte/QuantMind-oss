/**
 * 策略模板
 * 提供常用的交易策略模板
 */

import { Strategy } from '../../types/backtest';

/**
 * 双均线策略
 */
export const doubleSMAStrategy: Strategy = {
  name: '双均线策略',
  version: '1.0.0',
  description: '快速均线上穿慢速均线时买入，下穿时卖出',
  parameters: [
    {
      name: 'fastPeriod',
      type: 'number',
      value: 10,
      min: 5,
      max: 50,
      step: 1,
      description: '快速均线周期'
    },
    {
      name: 'slowPeriod',
      type: 'number',
      value: 30,
      min: 20,
      max: 200,
      step: 5,
      description: '慢速均线周期'
    }
  ],
  code: `
// 双均线策略
function onBar(bar, context) {
  const fastPeriod = 10;
  const slowPeriod = 30;

  const fastSMA = context.indicators.sma(fastPeriod);
  const slowSMA = context.indicators.sma(slowPeriod);

  const currentIndex = context.barIndex;

  if (currentIndex < slowPeriod) return;

  const prevFast = fastSMA[currentIndex - 1];
  const prevSlow = slowSMA[currentIndex - 1];
  const currFast = fastSMA[currentIndex];
  const currSlow = slowSMA[currentIndex];

  // 金叉买入
  if (prevFast < prevSlow && currFast > currSlow && !context.position) {
    const size = Math.floor(context.capital / bar.close);
    context.buy(size);
  }

  // 死叉卖出
  if (prevFast > prevSlow && currFast < currSlow && context.position) {
    context.closePosition();
  }
}
  `,
  onBar: (bar, context) => {
    const params = doubleSMAStrategy.parameters;
    const fastPeriod = params.find(p => p.name === 'fastPeriod')?.value || 10;
    const slowPeriod = params.find(p => p.name === 'slowPeriod')?.value || 30;

    const fastSMA = context.indicators.sma(fastPeriod);
    const slowSMA = context.indicators.sma(slowPeriod);

    const currentIndex = context.barIndex;

    if (currentIndex < slowPeriod) return;

    const prevFast = fastSMA[currentIndex - 1];
    const prevSlow = slowSMA[currentIndex - 1];
    const currFast = fastSMA[currentIndex];
    const currSlow = slowSMA[currentIndex];

    // 金叉买入
    if (prevFast < prevSlow && currFast > currSlow && !context.position) {
      const size = Math.floor(context.capital / bar.close);
      if (size > 0) {
        context.buy(size);
      }
    }

    // 死叉卖出
    if (prevFast > prevSlow && currFast < currSlow && context.position) {
      context.closePosition();
    }
  }
};

/**
 * MACD策略
 */
export const macdStrategy: Strategy = {
  name: 'MACD策略',
  version: '1.0.0',
  description: 'MACD线上穿信号线时买入，下穿时卖出',
  parameters: [
    {
      name: 'fastPeriod',
      type: 'number',
      value: 12,
      min: 5,
      max: 30,
      step: 1,
      description: '快速EMA周期'
    },
    {
      name: 'slowPeriod',
      type: 'number',
      value: 26,
      min: 20,
      max: 50,
      step: 1,
      description: '慢速EMA周期'
    },
    {
      name: 'signalPeriod',
      type: 'number',
      value: 9,
      min: 5,
      max: 20,
      step: 1,
      description: '信号线周期'
    }
  ],
  onBar: (bar, context) => {
    const currentIndex = context.barIndex;

    if (currentIndex < 26) return;

    const { macd, signal } = context.indicators.macd();

    const prevMACD = macd[currentIndex - 1];
    const prevSignal = signal[currentIndex - 1];
    const currMACD = macd[currentIndex];
    const currSignal = signal[currentIndex];

    // 金叉买入
    if (prevMACD < prevSignal && currMACD > currSignal && !context.position) {
      const size = Math.floor(context.capital / bar.close);
      if (size > 0) {
        context.buy(size);
      }
    }

    // 死叉卖出
    if (prevMACD > prevSignal && currMACD < currSignal && context.position) {
      context.closePosition();
    }
  }
};

/**
 * RSI策略
 */
export const rsiStrategy: Strategy = {
  name: 'RSI策略',
  version: '1.0.0',
  description: 'RSI低于超卖线时买入，高于超买线时卖出',
  parameters: [
    {
      name: 'period',
      type: 'number',
      value: 14,
      min: 7,
      max: 28,
      step: 1,
      description: 'RSI周期'
    },
    {
      name: 'oversold',
      type: 'number',
      value: 30,
      min: 20,
      max: 40,
      step: 5,
      description: '超卖线'
    },
    {
      name: 'overbought',
      type: 'number',
      value: 70,
      min: 60,
      max: 80,
      step: 5,
      description: '超买线'
    }
  ],
  onBar: (bar, context) => {
    const params = rsiStrategy.parameters;
    const period = params.find(p => p.name === 'period')?.value || 14;
    const oversold = params.find(p => p.name === 'oversold')?.value || 30;
    const overbought = params.find(p => p.name === 'overbought')?.value || 70;

    const currentIndex = context.barIndex;

    if (currentIndex < period + 1) return;

    const rsi = context.indicators.rsi(period);
    const currentRSI = rsi[currentIndex];
    const prevRSI = rsi[currentIndex - 1];

    // RSI从超卖区上穿时买入
    if (prevRSI < oversold && currentRSI >= oversold && !context.position) {
      const size = Math.floor(context.capital / bar.close);
      if (size > 0) {
        context.buy(size);
      }
    }

    // RSI从超买区下穿时卖出
    if (prevRSI > overbought && currentRSI <= overbought && context.position) {
      context.closePosition();
    }
  }
};

/**
 * 布林带策略
 */
export const bollingerStrategy: Strategy = {
  name: '布林带策略',
  version: '1.0.0',
  description: '价格触及下轨时买入，触及上轨时卖出',
  parameters: [
    {
      name: 'period',
      type: 'number',
      value: 20,
      min: 10,
      max: 50,
      step: 5,
      description: '布林带周期'
    },
    {
      name: 'stdDev',
      type: 'number',
      value: 2,
      min: 1,
      max: 3,
      step: 0.5,
      description: '标准差倍数'
    }
  ],
  onBar: (bar, context) => {
    const params = bollingerStrategy.parameters;
    const period = params.find(p => p.name === 'period')?.value || 20;
    const stdDev = params.find(p => p.name === 'stdDev')?.value || 2;

    const currentIndex = context.barIndex;

    if (currentIndex < period) return;

    const bollinger = context.indicators.bollinger(period, stdDev);
    const upper = bollinger.upper[currentIndex];
    const lower = bollinger.lower[currentIndex];

    // 价格触及下轨时买入
    if (bar.low <= lower && !context.position) {
      const size = Math.floor(context.capital / bar.close);
      if (size > 0) {
        context.buy(size);
      }
    }

    // 价格触及上轨时卖出
    if (bar.high >= upper && context.position) {
      context.closePosition();
    }
  }
};

/**
 * 海龟交易策略
 */
export const turtleStrategy: Strategy = {
  name: '海龟交易策略',
  version: '1.0.0',
  description: '突破20日高点买入，跌破10日低点止损',
  parameters: [
    {
      name: 'entryPeriod',
      type: 'number',
      value: 20,
      min: 10,
      max: 50,
      step: 5,
      description: '入场周期'
    },
    {
      name: 'exitPeriod',
      type: 'number',
      value: 10,
      min: 5,
      max: 20,
      step: 5,
      description: '出场周期'
    },
    {
      name: 'atrPeriod',
      type: 'number',
      value: 20,
      min: 10,
      max: 30,
      step: 5,
      description: 'ATR周期'
    }
  ],
  onBar: (bar, context) => {
    const params = turtleStrategy.parameters;
    const entryPeriod = params.find(p => p.name === 'entryPeriod')?.value || 20;
    const exitPeriod = params.find(p => p.name === 'exitPeriod')?.value || 10;
    const atrPeriod = params.find(p => p.name === 'atrPeriod')?.value || 20;

    const currentIndex = context.barIndex;

    if (currentIndex < entryPeriod) return;

    // 计算入场突破点
    const entryHigh = Math.max(...context.bars.slice(-entryPeriod).map(b => b.high));

    // 计算出场突破点
    const exitLow = Math.min(...context.bars.slice(-exitPeriod).map(b => b.low));

    // 计算ATR用于仓位控制
    const atr = context.indicators.atr(atrPeriod);
    const currentATR = atr[currentIndex];

    // 突破入场
    if (bar.close > entryHigh && !context.position) {
      // 根据ATR计算仓位大小
      const riskAmount = context.capital * 0.02; // 2%风险
      const size = Math.floor(riskAmount / (2 * currentATR));

      if (size > 0) {
        context.buy(size);
      }
    }

    // 跌破出场
    if (bar.close < exitLow && context.position) {
      context.closePosition();
    }
  }
};

/**
 * 获取所有策略模板
 */
export function getAllStrategyTemplates(): Strategy[] {
  return [
    doubleSMAStrategy,
    macdStrategy,
    rsiStrategy,
    bollingerStrategy,
    turtleStrategy
  ];
}

/**
 * 根据名称获取策略模板
 */
export function getStrategyTemplate(name: string): Strategy | undefined {
  return getAllStrategyTemplates().find(s => s.name === name);
}
