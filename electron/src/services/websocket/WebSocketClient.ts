/**
 * WebSocket客户端 - Week 9 Day 1
 * 提供完整的WebSocket连接管理、重连、心跳、消息队列功能
 */

export enum ConnectionState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  FAILED = 'FAILED'
}

export interface WebSocketClientConfig {
  url: string;
  reconnect?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  timeout?: number;
  debug?: boolean;
}

export interface WebSocketEvent {
  event: string;
  data: unknown;
  timestamp: number;
}

export type EventCallback = (data: unknown) => void;
export type StateCallback = (state: ConnectionState) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: Required<WebSocketClientConfig>;
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts = 0;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private lastHeartbeat: number = 0;
  private messageQueue: Array<{ type: string; data: unknown }> = [];
  private eventHandlers = new Map<string, Set<EventCallback>>();
  private stateHandlers = new Set<StateCallback>();
  private subscriptions = new Map<string, Set<EventCallback>>();

  constructor(config: WebSocketClientConfig) {
    this.config = {
      reconnect: true,
      reconnectDelay: 1000,
      maxReconnectAttempts: 5,
      heartbeatInterval: 30000,
      timeout: 10000,
      debug: false,
      ...config
    };
  }

  /**
   * 连接WebSocket服务器
   */
  async connect(): Promise<void> {
    if (this.state === ConnectionState.CONNECTED || this.state === ConnectionState.CONNECTING) {
      this.log('Already connected or connecting');
      return;
    }

    return new Promise((resolve, reject) => {
      this.setState(ConnectionState.CONNECTING);
      this.log(`Connecting to ${this.config.url}`);

      try {
        this.ws = new WebSocket(this.config.url);

        const timeout = setTimeout(() => {
          if (this.state === ConnectionState.CONNECTING) {
            this.ws?.close();
            reject(new Error('Connection timeout'));
          }
        }, this.config.timeout);

        this.ws.onopen = () => {
          clearTimeout(timeout);
          this.log('Connected successfully');
          this.setState(ConnectionState.CONNECTED);
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.flushMessageQueue();
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          clearTimeout(timeout);
          this.log(`Connection closed: ${event.code} ${event.reason}`);
          this.stopHeartbeat();

          if (event.code !== 1000 && this.config.reconnect && this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.attemptReconnect();
          } else {
            this.setState(ConnectionState.DISCONNECTED);
          }
        };

        this.ws.onerror = (error) => {
          clearTimeout(timeout);
          this.log('Connection error:', error);
          reject(error);
        };

      } catch (error) {
        this.log('Failed to create WebSocket:', error);
        this.setState(ConnectionState.FAILED);
        reject(error);
      }
    });
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.config.reconnect = false;
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setState(ConnectionState.DISCONNECTED);
    this.messageQueue = [];
  }

  /**
   * 发送消息
   */
  send(type: string, data: unknown): boolean {
    const message = {
      type,
      data,
      timestamp: Date.now()
    };

    if (this.state === ConnectionState.CONNECTED && this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        this.log('Sent message:', type);
        return true;
      } catch (error) {
        this.log('Failed to send message:', error);
        this.messageQueue.push(message);
        return false;
      }
    } else {
      // 放入消息队列
      this.messageQueue.push(message);
      this.log('Message queued:', type);
      return false;
    }
  }

  /**
   * 订阅事件
   */
  on(event: string, callback: EventCallback): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    this.eventHandlers.get(event)!.add(callback);
    this.log(`Event handler registered: ${event}`);
  }

  /**
   * 取消订阅事件
   */
  off(event: string, callback?: EventCallback): void {
    if (callback) {
      this.eventHandlers.get(event)?.delete(callback);
    } else {
      this.eventHandlers.delete(event);
    }
    this.log(`Event handler removed: ${event}`);
  }

  /**
   * 订阅频道
   */
  subscribe(channel: string, callback: EventCallback): string {
    const subscriptionId = `${channel}_${Date.now()}_${Math.random()}`;

    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
      // 发送订阅请求
      this.send('subscribe', { channel });
    }

    this.subscriptions.get(channel)!.add(callback);
    this.log(`Subscribed to channel: ${channel}`);

    return subscriptionId;
  }

  /**
   * 取消订阅频道
   */
  unsubscribe(channel: string): void {
    if (this.subscriptions.has(channel)) {
      this.subscriptions.delete(channel);
      // 发送取消订阅请求
      this.send('unsubscribe', { channel });
      this.log(`Unsubscribed from channel: ${channel}`);
    }
  }

  /**
   * 监听连接状态变化
   */
  onStateChange(callback: StateCallback): void {
    this.stateHandlers.add(callback);
  }

  /**
   * 取消监听连接状态
   */
  offStateChange(callback: StateCallback): void {
    this.stateHandlers.delete(callback);
  }

  /**
   * 获取当前状态
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * 获取连接信息
   */
  getConnectionInfo() {
    return {
      state: this.state,
      url: this.config.url,
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.config.maxReconnectAttempts,
      queuedMessages: this.messageQueue.length,
      subscriptions: Array.from(this.subscriptions.keys()),
      lastHeartbeat: this.lastHeartbeat,
      isConnected: this.state === ConnectionState.CONNECTED
    };
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      const { type, data: payload } = message;

      this.log('Received message:', type);

      // 处理心跳响应
      if (type === 'heartbeat' || type === 'pong') {
        this.lastHeartbeat = Date.now();
        return;
      }

      // 触发事件处理器
      const handlers = this.eventHandlers.get(type);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(payload);
          } catch (error) {
            this.log('Error in event handler:', error);
          }
        });
      }

      // 触发频道订阅回调
      const channelHandlers = this.subscriptions.get(type);
      if (channelHandlers) {
        channelHandlers.forEach(handler => {
          try {
            handler(payload);
          } catch (error) {
            this.log('Error in channel handler:', error);
          }
        });
      }

    } catch (error) {
      this.log('Failed to parse message:', error);
    }
  }

  /**
   * 尝试重连
   */
  private attemptReconnect(): void {
    this.reconnectAttempts++;
    this.setState(ConnectionState.RECONNECTING);

    const delay = Math.min(
      this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000 // 最大30秒
    );

    this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`);

    setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        this.log('Reconnection failed:', error);

        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
          this.log('Max reconnection attempts reached');
          this.setState(ConnectionState.FAILED);
        }
      }
    }, delay);
  }

  /**
   * 开始心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastHeartbeat = Date.now();

    this.heartbeatTimer = setInterval(() => {
      if (this.state === ConnectionState.CONNECTED) {
        this.send('heartbeat', { ping: true });

        // 检查心跳超时
        const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
        if (timeSinceLastHeartbeat > this.config.heartbeatInterval * 2) {
          this.log('Heartbeat timeout, reconnecting...');
          this.ws?.close();
        }
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * 刷新消息队列
   */
  private flushMessageQueue(): void {
    if (this.messageQueue.length > 0) {
      this.log(`Flushing ${this.messageQueue.length} queued messages`);

      const messages = [...this.messageQueue];
      this.messageQueue = [];

      messages.forEach(({ type, data }) => {
        this.send(type, data);
      });
    }
  }

  /**
   * 设置连接状态
   */
  private setState(state: ConnectionState): void {
    if (this.state !== state) {
      const oldState = this.state;
      this.state = state;
      this.log(`State changed: ${oldState} -> ${state}`);

      this.stateHandlers.forEach(handler => {
        try {
          handler(state);
        } catch (error) {
          this.log('Error in state handler:', error);
        }
      });
    }
  }

  /**
   * 日志输出
   */
  private log(...args: unknown[]): void {
    if (this.config.debug) {
      console.log('[WebSocketClient]', ...args);
    }
  }
}

export default WebSocketClient;
