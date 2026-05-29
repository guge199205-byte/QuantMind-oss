/**
 * Binance API测试
 */

import { vi } from 'vitest';
import { BinanceAPI } from '../binance/BinanceAPI';
import type { ExchangeConfig } from '../base/types';

describe('BinanceAPI', () => {
  let api: BinanceAPI;

  beforeEach(() => {
    const config: ExchangeConfig = {
      apiKey: 'test_api_key',
      apiSecret: 'test_api_secret',
      testnet: true
    };

    api = new BinanceAPI(config);
  });

  describe('市场数据', () => {
    it('应该能获取K线数据', async () => {
      vi.spyOn(api as unknown as { get: (...args: unknown[]) => Promise<unknown> }, 'get').mockResolvedValue({
        success: true,
        data: [
          [1710000000000, '50000', '51000', '49000', '50500', '100']
        ]
      });

      const result = await api.getKlines('BTCUSDT', '1h', 10);

      expect(result.success).toBe(true);
      if (result.data) {
        expect(Array.isArray(result.data)).toBe(true);
        expect(result.data.length).toBeGreaterThan(0);

        const kline = result.data[0];
        expect(kline).toHaveProperty('timestamp');
        expect(kline).toHaveProperty('open');
        expect(kline).toHaveProperty('high');
        expect(kline).toHaveProperty('low');
        expect(kline).toHaveProperty('close');
        expect(kline).toHaveProperty('volume');
      }
    }, 10000);

    it('应该能获取24h行情', async () => {
      vi.spyOn(api as unknown as { get: (...args: unknown[]) => Promise<unknown> }, 'get').mockResolvedValue({
        success: true,
        data: {
          symbol: 'BTCUSDT',
          priceChange: '100.1',
          priceChangePercent: '1.2',
          lastPrice: '50100.5',
          highPrice: '51000',
          lowPrice: '49000',
          volume: '1000',
          quoteVolume: '50000000',
        }
      });

      const result = await api.getTicker24h('BTCUSDT');

      expect(result.success).toBe(true);
      if (result.data) {
        const raw = result.data as unknown;
        const ticker = Array.isArray(raw) ? (raw[0] as Record<string, unknown>) : (raw as Record<string, unknown>);
        expect(ticker).toHaveProperty('symbol');
        expect(ticker).toHaveProperty('lastPrice');
        expect(ticker).toHaveProperty('priceChange');
        expect(ticker).toHaveProperty('volume');
      }
    }, 10000);

    it('应该能获取订单簿', async () => {
      vi.spyOn(api as unknown as { get: (...args: unknown[]) => Promise<unknown> }, 'get').mockResolvedValue({
        success: true,
        data: {
          bids: [['50000', '1.2']],
          asks: [['50010', '0.8']],
        }
      });

      const result = await api.getOrderBook('BTCUSDT', 10);

      expect(result.success).toBe(true);
      if (result.data) {
        expect(result.data).toHaveProperty('bids');
        expect(result.data).toHaveProperty('asks');
        expect(Array.isArray(result.data.bids)).toBe(true);
        expect(Array.isArray(result.data.asks)).toBe(true);
      }
    }, 10000);
  });

  describe('速率限制', () => {
    it('应该能在并发请求下稳定返回', async () => {
      vi.spyOn(api as unknown as { get: (...args: unknown[]) => Promise<unknown> }, 'get').mockResolvedValue({
        success: true,
        data: {
          symbol: 'BTCUSDT',
          priceChange: '0',
          priceChangePercent: '0',
          lastPrice: '50000',
          highPrice: '50000',
          lowPrice: '50000',
          volume: '1',
          quoteVolume: '50000',
        }
      });

      const promises = [];
      for (let i = 0; i < 5; i++) {
        promises.push(api.getTicker24h('BTCUSDT'));
      }

      const results = await Promise.all(promises);
      expect(results.every((r) => r.success)).toBe(true);
    }, 15000);
  });
});
