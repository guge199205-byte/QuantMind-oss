import React, { createContext, useContext, useMemo } from 'react';
import { WebSocketStatus, SubscriptionConfig, MessageType } from '../services/websocketService';
import { useWebSocket as useWebSocketInternal } from '../hooks/useWebSocketInternal';

interface WebSocketContextType {
  status: WebSocketStatus;
  isConnected: boolean;
  connectionInfo: any;
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribe: (config: SubscriptionConfig) => void;
  unsubscribe: (symbols: string[]) => void;
  send: (type: MessageType, data: any) => boolean;
  onMessage: (callback: (type: MessageType, data: any) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const disableWebSocket =
    String((import.meta as any).env?.VITE_DISABLE_WEBSOCKET || '').toLowerCase() === 'true';
  const ws = useWebSocketInternal({ autoConnect: !disableWebSocket });

  const contextValue = useMemo(() => ({
    ...ws
  }), [ws]);

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket必须在WebSocketProvider中使用');
  }
  return context;
};
