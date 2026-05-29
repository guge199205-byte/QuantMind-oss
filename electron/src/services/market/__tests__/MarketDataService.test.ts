/**
 * MarketDataService单元测试 - Week 9 Day 1
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { MarketDataService, Quote } from '../MarketDataService';
import { ConnectionState } from '../../websocket/WebSocketClient';

// Mock WebSocket
class MockWebSocket {
  readyState = WebSocket.CONNECTING;
  url: string;
  onopen: ((event: any) => void) | null = null;
  onclose: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen({});
      }
    }, 10);
  }

  send(_data: string) {
    // Mock send
  }

  close(code?: number, reason?: string) {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose({ code: code || 1000, reason: reason || '', wasClean: true });
    }
  }
}

global.WebSocket = MockWebSocket as any;

describe('MarketDataService', () => {
  let service: MarketDataService;

  beforeEach(() => {
    service = new MarketDataService('ws://localhost:8080', false);
  });

  afterEach(() => {
    service.disconnect();
  });

  describe('连接管理', () => {
    it('应该能够连接到服务器', async () => {
      await service.connect();
      expect(service.getConnectionState()).toBe(ConnectionState.CONNECTED);
    });

    it('应该能够断开连接', async () => {
      await service.connect();
      service.disconnect();
      expect(service.getConnectionState()).toBe(ConnectionState.DISCONNECTED);
    });

    it('应该能够获取连接信息', async () => {
      await service.connect();
      const info = service.getConnectionInfo();
      expect(info.state).toBe(ConnectionState.CONNECTED);
      expect(info.isConnected).toBe(true);
    });
  });

  describe('行情订阅', () => {
    it('应该能够订阅实时行情', async () => {
      const callback = vi.fn();
      await service.connect();

      const subscriptionId = service.subscribeQuote('000001', callback);
      expect(subscriptionId).toBeTruthy();
    });

    it('应该能够接收行情数据', async () => {
      let receivedQuote: Quote | null = null;

      await service.connect();
      service.subscribeQuote('000001', (quote) => {
        receivedQuote = quote;
      });

      // 模拟接收行情数据
      const ws = (service as any).wsClient.ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'quote:000001',
            data: {
              name: '平安银行',
              price: 10.5,
              open: 10.3,
              high: 10.6,
              low: 10.2,
              close: 10.4,
              volume: 1000000,
              amount: 10500000,
              change: 0.1,
              changePercent: 0.96,
              timestamp: Date.now()
            }
          })
        });
      }

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(receivedQuote).toBeTruthy();
      expect(receivedQuote?.symbol).toBe('000001');
      expect(receivedQuote?.price).toBe(10.5);
    });

    it('应该能够取消订阅', async () => {
      const callback = vi.fn();
      await service.connect();

      service.subscribeQuote('000001', callback);
      service.unsubscribeQuote('000001');

      // 模拟接收行情数据
      const ws = (service as any).wsClient.ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'quote:000001',
            data: { price: 10.5 }
          })
        });
      }

      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe('Tick数据', () => {
    it('应该能够订阅Tick数据', async () => {
      const callback = vi.fn();
      await service.connect();

      service.subscribeTick('000001', callback);

      // 模拟接收Tick数据
      const ws = (service as any).wsClient.ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'tick:000001',
            data: {
              price: 10.5,
              volume: 100,
              direction: 'up',
              timestamp: Date.now()
            }
          })
        });
      }

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(callback).toHaveBeenCalled();
    });

    it('应该能够获取Tick历史数据', async () => {
      await service.connect();
      service.subscribeTick('000001', () => {});

      // 模拟接收多个Tick
      const ws = (service as any).wsClient.ws;
      for (let i = 0; i < 5; i++) {
        if (ws.onmessage) {
          ws.onmessage({
            data: JSON.stringify({
              type: 'tick:000001',
              data: {
                price: 10.5 + i * 0.1,
                volume: 100,
                direction: 'up',
                timestamp: Date.now() + i
              }
            })
          });
        }
      }

      await new Promise(resolve => setTimeout(resolve, 50));

      const ticks = service.getTickData('000001');
      expect(ticks.length).toBe(5);
    });
  });

  describe('成交明细', () => {
    it('应该能够订阅成交明细', async () => {
      const callback = vi.fn();
      await service.connect();

      service.subscribeTrade('000001', callback);

      // 模拟接收成交明细
      const ws = (service as any).wsClient.ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'trade:000001',
            data: {
              price: 10.5,
              volume: 100,
              amount: 1050,
              type: 'buy',
              timestamp: Date.now()
            }
          })
        });
      }

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(callback).toHaveBeenCalled();
    });
  });

  describe('数据管理', () => {
    it('应该能够获取最新行情', async () => {
      await service.connect();
      service.subscribeQuote('000001', () => {});

      // 模拟接收行情
      const ws = (service as any).wsClient.ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'quote:000001',
            data: {
              name: '平安银行',
              price: 10.5,
              open: 10.3,
              timestamp: Date.now()
            }
          })
        });
      }

      await new Promise(resolve => setTimeout(resolve, 50));

      const quote = service.getLatestQuote('000001');
      expect(quote).toBeTruthy();
      expect(quote?.price).toBe(10.5);
    });

    it('未订阅的股票应该返回null', () => {
      const quote = service.getLatestQuote('999999');
      expect(quote).toBeNull();
    });
  });
});
