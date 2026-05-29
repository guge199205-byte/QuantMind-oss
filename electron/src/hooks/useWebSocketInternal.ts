import { useState, useEffect, useCallback, useRef } from 'react';
import { websocketService, WebSocketStatus, MessageType, SubscriptionConfig } from '../services/websocketService';

export interface UseWebSocketOptions {
  autoConnect?: boolean;
  subscriptions?: SubscriptionConfig;
  onStatusChange?: (status: WebSocketStatus) => void;
}

export interface UseWebSocketReturn {
  status: WebSocketStatus;
  isConnected: boolean;
  connectionInfo: ReturnType<typeof websocketService.getConnectionInfo>;
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribe: (config: SubscriptionConfig) => void;
  unsubscribe: (symbols: string[]) => void;
  send: (type: MessageType, data: unknown) => boolean;
  onMessage: (callback: (type: MessageType, data: unknown) => void) => () => void;
}

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    autoConnect = false,
    subscriptions,
    onStatusChange
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>(websocketService.getStatus());
  const [connectionInfo, setConnectionInfo] = useState(websocketService.getConnectionInfo());

  // 使用ref存储回调函数，避免重复添加/移除处理器
  const onMessageCallbacks = useRef<((type: MessageType, data: unknown) => void)[]>([]);
  const onStatusChangeRef = useRef(onStatusChange);

  // 更新ref
  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  // 状态变化处理器
  const handleStatusChange = useCallback((newStatus: WebSocketStatus) => {
    setStatus(newStatus);
    setConnectionInfo(websocketService.getConnectionInfo());
    onStatusChangeRef.current?.(newStatus);
  }, []);

  // 消息处理器
  const handleMessage = useCallback((data: unknown) => {
    onMessageCallbacks.current.forEach(cb => cb(MessageType.MARKET_DATA, data));
  }, []);

  const onMessage = useCallback((callback: (type: MessageType, data: unknown) => void) => {
    onMessageCallbacks.current.push(callback);
    // 返回一个取消注册的函数
    return () => {
      onMessageCallbacks.current = onMessageCallbacks.current.filter(cb => cb !== callback);
    };
  }, []);

  // 连接WebSocket
  const connect = useCallback(async () => {
    try {
      await websocketService.connect();

      // 自动订阅
      if (subscriptions) {
        websocketService.subscribe(subscriptions);
      }
    } catch (error) {
      console.error('WebSocket连接失败:', error);
    }
  }, [subscriptions]);

  // 断开连接
  const disconnect = useCallback(() => {
    websocketService.disconnect();
  }, []);

  // 订阅数据
  const subscribe = useCallback((config: SubscriptionConfig) => {
    websocketService.subscribe(config);
  }, []);

  // 取消订阅
  const unsubscribe = useCallback((symbols: string[]) => {
    websocketService.unsubscribe(symbols);
  }, []);

  // 发送消息
  const send = useCallback((type: MessageType, data: unknown) => {
    return websocketService.send({
      type,
      timestamp: new Date().toISOString(),
      data
    });
  }, []);

  // 设置事件处理器
  useEffect(() => {
    // 添加状态变化处理器
    websocketService.addStatusHandler(handleStatusChange);

    // 添加市场数据消息处理器
    websocketService.addMessageHandler(MessageType.MARKET_DATA, handleMessage);

    // 自动连接
    if (autoConnect && status === WebSocketStatus.DISCONNECTED) {
      connect();
    }

    return () => {
      // 清理处理器
      websocketService.removeStatusHandler(handleStatusChange);
      websocketService.removeMessageHandler(MessageType.MARKET_DATA, handleMessage);
    };
  }, [autoConnect, connect, handleMessage, handleStatusChange]);

  return {
    status,
    isConnected: status === WebSocketStatus.CONNECTED,
    connectionInfo,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send,
    onMessage
  };
};
