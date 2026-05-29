/**
 * WebSocket Hook - Week 9 Day 1
 * 提供React组件中使用WebSocket的便捷Hook
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { WebSocketClient, ConnectionState, EventCallback } from '../../services/websocket/WebSocketClient';

export interface UseWebSocketOptions {
  url: string;
  reconnect?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  autoConnect?: boolean;
  debug?: boolean;
}

export interface UseWebSocketReturn {
  state: ConnectionState;
  connect: () => Promise<void>;
  disconnect: () => void;
  send: (type: string, data: any) => boolean;
  subscribe: (channel: string, callback: EventCallback) => string;
  unsubscribe: (channel: string) => void;
  on: (event: string, callback: EventCallback) => void;
  off: (event: string, callback?: EventCallback) => void;
  isConnected: boolean;
  connectionInfo: any;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const [state, setState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
  const [connectionInfo, setConnectionInfo] = useState<any>({});
  const clientRef = useRef<WebSocketClient | null>(null);

  // 初始化WebSocket客户端
  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = new WebSocketClient({
        url: options.url,
        reconnect: options.reconnect ?? true,
        reconnectDelay: options.reconnectDelay ?? 1000,
        maxReconnectAttempts: options.maxReconnectAttempts ?? 5,
        heartbeatInterval: options.heartbeatInterval ?? 30000,
        debug: options.debug ?? false
      });

      // 监听状态变化
      clientRef.current.onStateChange((newState) => {
        setState(newState);
        setConnectionInfo(clientRef.current!.getConnectionInfo());
      });

      // 自动连接
      if (options.autoConnect !== false) {
        clientRef.current.connect().catch((error) => {
          console.error('Failed to auto-connect:', error);
        });
      }
    }

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
        clientRef.current = null;
      }
    };
  }, [options.url]);

  const connect = useCallback(async () => {
    if (clientRef.current) {
      await clientRef.current.connect();
    }
  }, []);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
  }, []);

  const send = useCallback((type: string, data: any): boolean => {
    if (clientRef.current) {
      return clientRef.current.send(type, data);
    }
    return false;
  }, []);

  const subscribe = useCallback((channel: string, callback: EventCallback): string => {
    if (clientRef.current) {
      return clientRef.current.subscribe(channel, callback);
    }
    return '';
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    if (clientRef.current) {
      clientRef.current.unsubscribe(channel);
    }
  }, []);

  const on = useCallback((event: string, callback: EventCallback) => {
    if (clientRef.current) {
      clientRef.current.on(event, callback);
    }
  }, []);

  const off = useCallback((event: string, callback?: EventCallback) => {
    if (clientRef.current) {
      clientRef.current.off(event, callback);
    }
  }, []);

  return {
    state,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    on,
    off,
    isConnected: state === ConnectionState.CONNECTED,
    connectionInfo
  };
}

export default useWebSocket;
