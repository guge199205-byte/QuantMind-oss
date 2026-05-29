/**
 * WebSocketClient单元测试 - Week 9 Day 1
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { WebSocketClient, ConnectionState } from '../WebSocketClient';

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

// 设置全局WebSocket mock
global.WebSocket = MockWebSocket as any;

describe('WebSocketClient', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    client = new WebSocketClient({
      url: 'ws://localhost:8080',
      debug: false
    });
  });

  afterEach(() => {
    client.disconnect();
  });

  describe('连接管理', () => {
    it('应该能够成功连接', async () => {
      await client.connect();
      expect(client.getState()).toBe(ConnectionState.CONNECTED);
    });

    it('应该能够断开连接', async () => {
      await client.connect();
      client.disconnect();
      expect(client.getState()).toBe(ConnectionState.DISCONNECTED);
    });

    it('应该能够获取连接信息', async () => {
      await client.connect();
      const info = client.getConnectionInfo();
      expect(info.state).toBe(ConnectionState.CONNECTED);
      expect(info.url).toBe('ws://localhost:8080');
      expect(info.isConnected).toBe(true);
    });
  });

  describe('事件系统', () => {
    it('应该能够注册和触发事件处理器', async () => {
      const handler = vi.fn();
      client.on('test_event', handler);
      await client.connect();

      // 模拟接收消息
      const ws = (client as any).ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'test_event',
            data: { message: 'test' }
          })
        });
      }

      expect(handler).toHaveBeenCalledWith({ message: 'test' });
    });

    it('应该能够移除事件处理器', async () => {
      const handler = vi.fn();
      client.on('test_event', handler);
      client.off('test_event', handler);
      await client.connect();

      // 模拟接收消息
      const ws = (client as any).ws;
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'test_event',
            data: { message: 'test' }
          })
        });
      }

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('频道订阅', () => {
    it('应该能够订阅频道', async () => {
      const callback = vi.fn();
      await client.connect();
      client.subscribe('test_channel', callback);

      const info = client.getConnectionInfo();
      expect(info.subscriptions).toContain('test_channel');
    });

    it('应该能够取消订阅频道', async () => {
      const callback = vi.fn();
      await client.connect();
      client.subscribe('test_channel', callback);
      client.unsubscribe('test_channel');

      const info = client.getConnectionInfo();
      expect(info.subscriptions).not.toContain('test_channel');
    });
  });

  describe('消息队列', () => {
    it('未连接时消息应该进入队列', () => {
      const result = client.send('test', { data: 'test' });
      expect(result).toBe(false);

      const info = client.getConnectionInfo();
      expect(info.queuedMessages).toBe(1);
    });

    it('连接后应该刷新消息队列', async () => {
      client.send('test1', { data: 'test1' });
      client.send('test2', { data: 'test2' });

      await client.connect();

      // 等待消息队列刷新
      await new Promise(resolve => setTimeout(resolve, 50));

      const info = client.getConnectionInfo();
      expect(info.queuedMessages).toBe(0);
    });
  });

  describe('状态监听', () => {
    it('应该能够监听状态变化', async () => {
      const stateHandler = vi.fn();
      client.onStateChange(stateHandler);

      await client.connect();

      expect(stateHandler).toHaveBeenCalledWith(ConnectionState.CONNECTING);
      expect(stateHandler).toHaveBeenCalledWith(ConnectionState.CONNECTED);
    });

    it('应该能够取消状态监听', async () => {
      const stateHandler = vi.fn();
      client.onStateChange(stateHandler);
      client.offStateChange(stateHandler);

      await client.connect();

      // 由于已经取消监听,不应该被调用(或只在取消前被调用)
      expect(stateHandler).not.toHaveBeenCalledWith(ConnectionState.CONNECTED);
    });
  });
});
