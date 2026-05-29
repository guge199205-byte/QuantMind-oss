/**
 * 存储服务测试
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { KlineStorage, TradeStorage, ConfigStorage } from '../index';

describe('KlineStorage', () => {
  let storage: KlineStorage;

  beforeEach(async () => {
    storage = new KlineStorage();
    await storage.init();
  });

  afterEach(() => {
    storage.close();
  });

  it('应该能够保存K线数据', async () => {
    const kline = {
      symbol: 'BTCUSDT',
      interval: '1h',
      timestamp: Date.now(),
      open: 50000,
      high: 51000,
      low: 49000,
      close: 50500,
      volume: 100,
      closeTime: Date.now(),
      quoteVolume: 5000000,
      trades: 1000,
      takerBuyBaseVolume: 60,
      takerBuyQuoteVolume: 3000000,
    };

    const id = await storage.saveKline(kline);
    expect(id).toBeGreaterThan(0);
  });

  it('应该能够获取K线统计', async () => {
    const stats = await storage.getKlineStats('BTCUSDT', '1h');
    expect(stats).toHaveProperty('count');
  });
});

describe('TradeStorage', () => {
  let storage: TradeStorage;

  beforeEach(async () => {
    storage = new TradeStorage();
    await storage.init();
  });

  afterEach(() => {
    storage.close();
  });

  it('应该能够保存交易记录', async () => {
    const trade = {
      orderId: 'ORDER123',
      symbol: 'BTCUSDT',
      side: 'BUY' as const,
      type: 'LIMIT',
      price: 50000,
      quantity: 0.1,
      quoteQuantity: 5000,
      commission: 5,
      commissionAsset: 'USDT',
      timestamp: Date.now(),
      isMaker: true,
    };

    const id = await storage.saveTrade(trade);
    expect(id).toBeGreaterThan(0);
  });

  it('应该能够保存订单记录', async () => {
    const order = {
      orderId: 'ORDER456',
      clientOrderId: 'CLIENT123',
      symbol: 'BTCUSDT',
      side: 'BUY' as const,
      type: 'LIMIT',
      quantity: 0.1,
      price: 50000,
      status: 'FILLED',
      executedQty: 0.1,
      cummulativeQuoteQty: 5000,
      timestamp: Date.now(),
      updateTime: Date.now(),
    };

    const id = await storage.saveOrder(order);
    expect(id).toBeGreaterThan(0);
  });
});

describe('ConfigStorage', () => {
  let storage: ConfigStorage;

  beforeEach(async () => {
    storage = new ConfigStorage();
    await storage.init();
  });

  afterEach(() => {
    storage.close();
  });

  it('应该能够保存策略配置', async () => {
    const strategy = {
      name: 'MA Cross',
      type: 'trend',
      symbol: 'BTCUSDT',
      interval: '1h',
      parameters: {
        fastPeriod: 10,
        slowPeriod: 20,
      },
      enabled: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    const id = await storage.saveStrategy(strategy);
    expect(id).toBeGreaterThan(0);
  });

  it('应该能够设置和获取配置', async () => {
    await storage.setConfig('theme', 'dark');
    const theme = await storage.getConfig('theme');
    expect(theme).toBe('dark');
  });

  it('应该能够导出配置', async () => {
    const exported = await storage.exportConfig();
    expect(exported).toHaveProperty('strategies');
    expect(exported).toHaveProperty('userConfig');
    expect(exported).toHaveProperty('exportTime');
  });
});
