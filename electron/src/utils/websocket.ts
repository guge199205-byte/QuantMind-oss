/**
 * WebSocket 连接管理工具
 *
 * 功能：
 * - 自动重连机制
 * - 心跳检测
 * - 连接状态管理
 * - 消息队列
 */

export enum WebSocketStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTING = 'disconnecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting',
}

export interface WebSocketMessage<T = any> {
  type: string;
  data: T;
  timestamp: number;
}

export interface WebSocketManagerOptions {
  url: string;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
  onStatusChange?: (status: WebSocketStatus) => void;
}

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private options: Required<WebSocketManagerOptions>;
  private status: WebSocketStatus = WebSocketStatus.DISCONNECTED;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private heartbeatTimeoutTimer: NodeJS.Timeout | null = null;
  private reconnectCount = 0;
  private messageQueue: WebSocketMessage[] = [];
  private lastHeartbeatTime = 0;

  constructor(options: WebSocketManagerOptions) {
    this.options = {
      reconnect: true,
      reconnectInterval: 3000,
      reconnectAttempts: 5,
      heartbeatInterval: 30000,
      heartbeatTimeout: 10000,
      onOpen: () => {},
      onClose: () => {},
      onError: () => {},
      onMessage: () => {},
      onStatusChange: () => {},
      ...options,
    };
  }

  /**
   * 连接 WebSocket
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.updateStatus(WebSocketStatus.CONNECTING);

      try {
        this.ws = new WebSocket(this.options.url);

        this.ws.onopen = (event) => {
          console.log('[WebSocket] Connected:', this.options.url);
          this.updateStatus(WebSocketStatus.CONNECTED);
          this.reconnectCount = 0;
          this.startHeartbeat();
          this.flushMessageQueue();
          this.options.onOpen(event);
          resolve();
        };

        this.ws.onclose = (event) => {
          console.log('[WebSocket] Closed:', event.code, event.reason);
          this.updateStatus(WebSocketStatus.DISCONNECTED);
          this.stopHeartbeat();
          this.options.onClose(event);

          // 自动重连
          if (this.options.reconnect && this.reconnectCount < this.options.reconnectAttempts) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (event) => {
          console.error('[WebSocket] Error:', event);
          this.updateStatus(WebSocketStatus.ERROR);
          this.options.onError(event);
          reject(new Error('WebSocket connection error'));
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);

            // 处理心跳响应
            if (message.type === 'pong') {
              this.lastHeartbeatTime = Date.now();
              this.resetHeartbeatTimeout();
              return;
            }

            this.options.onMessage(message);
          } catch (error) {
            console.error('[WebSocket] Failed to parse message:', error);
          }
        };
      } catch (error) {
        console.error('[WebSocket] Failed to create connection:', error);
        this.updateStatus(WebSocketStatus.ERROR);
        reject(error);
      }
    });
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.options.reconnect = false;
    this.clearReconnectTimer();
    this.stopHeartbeat();

    if (this.ws) {
      this.updateStatus(WebSocketStatus.DISCONNECTING);
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }

    this.updateStatus(WebSocketStatus.DISCONNECTED);
  }

  /**
   * 发送消息
   */
  send(type: string, data: any): boolean {
    const message: WebSocketMessage = {
      type,
      data,
      timestamp: Date.now(),
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('[WebSocket] Failed to send message:', error);
        this.messageQueue.push(message);
        return false;
      }
    } else {
      // 连接未就绪，加入队列
      this.messageQueue.push(message);
      return false;
    }
  }

  /**
   * 获取当前状态
   */
  getStatus(): WebSocketStatus {
    return this.status;
  }

  /**
   * 是否已连接
   */
  isConnected(): boolean {
    return this.status === WebSocketStatus.CONNECTED &&
           this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * 更新状态
   */
  private updateStatus(status: WebSocketStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.options.onStatusChange(status);
    }
  }

  /**
   * 定时重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    this.reconnectCount++;
    this.updateStatus(WebSocketStatus.RECONNECTING);

    const delay = this.options.reconnectInterval * Math.min(this.reconnectCount, 5);
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectCount}/${this.options.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect().catch(error => {
        console.error('[WebSocket] Reconnect failed:', error);
      });
    }, delay);
  }

  /**
   * 清除重连定时器
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * 启动心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.send('ping', { timestamp: Date.now() });

        // 设置心跳超时
        this.heartbeatTimeoutTimer = setTimeout(() => {
          console.warn('[WebSocket] Heartbeat timeout, reconnecting...');
          this.ws?.close();
        }, this.options.heartbeatTimeout);
      }
    }, this.options.heartbeatInterval);
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  /**
   * 重置心跳超时
   */
  private resetHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  /**
   * 发送队列中的消息
   */
  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0 && this.isConnected()) {
      const message = this.messageQueue.shift();
      if (message) {
        try {
          this.ws!.send(JSON.stringify(message));
        } catch (error) {
          console.error('[WebSocket] Failed to flush message:', error);
          this.messageQueue.unshift(message);
          break;
        }
      }
    }
  }

  /**
   * 清理资源
   */
  destroy(): void {
    this.disconnect();
    this.messageQueue = [];
  }
}

// ============================================================================
// React Hook
// ============================================================================

import { useEffect, useRef, useState } from 'react';

export interface UseWebSocketOptions extends Omit<WebSocketManagerOptions, 'url'> {
  enabled?: boolean;
}

export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
  const { enabled = true, ...managerOptions } = options;
  const [status, setStatus] = useState<WebSocketStatus>(WebSocketStatus.DISCONNECTED);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const managerRef = useRef<WebSocketManager | null>(null);

  useEffect(() => {
    if (!enabled || !url) {
      return;
    }

    const manager = new WebSocketManager({
      url,
      ...managerOptions,
      onStatusChange: (newStatus) => {
        setStatus(newStatus);
        managerOptions.onStatusChange?.(newStatus);
      },
      onMessage: (message) => {
        setLastMessage(message);
        managerOptions.onMessage?.(message);
      },
    });

    managerRef.current = manager;

    manager.connect().catch(error => {
      console.error('[useWebSocket] Connection failed:', error);
    });

    return () => {
      manager.destroy();
      managerRef.current = null;
    };
  }, [url, enabled]);

  const send = (type: string, data: any) => {
    return managerRef.current?.send(type, data) ?? false;
  };

  const disconnect = () => {
    managerRef.current?.disconnect();
  };

  const reconnect = () => {
    managerRef.current?.disconnect();
    setTimeout(() => {
      managerRef.current?.connect();
    }, 100);
  };

  return {
    status,
    lastMessage,
    send,
    disconnect,
    reconnect,
    isConnected: managerRef.current?.isConnected() ?? false,
  };
};
