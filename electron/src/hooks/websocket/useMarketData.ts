/**
 * 行情数据Hook - Week 9 Day 1
 * 提供React组件中订阅实时行情的便捷Hook
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { MarketDataService, Quote, Tick, Trade } from '../../services/market/MarketDataService';
import { ConnectionState } from '../../services/websocket/WebSocketClient';

export interface UseMarketDataOptions {
  url: string;
  symbols?: string[];
  autoConnect?: boolean;
  debug?: boolean;
}

export interface UseMarketDataReturn {
  connectionState: ConnectionState;
  quotes: Map<string, Quote>;
  ticks: Map<string, Tick[]>;
  trades: Map<string, Trade[]>;
  subscribeQuote: (symbol: string) => void;
  unsubscribeQuote: (symbol: string) => void;
  subscribeTick: (symbol: string) => void;
  unsubscribeTick: (symbol: string) => void;
  subscribeTrade: (symbol: string) => void;
  unsubscribeTrade: (symbol: string) => void;
  getLatestQuote: (symbol: string) => Quote | null;
  connect: () => Promise<void>;
  disconnect: () => void;
}

export function useMarketData(options: UseMarketDataOptions): UseMarketDataReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map());
  const [ticks, setTicks] = useState<Map<string, Tick[]>>(new Map());
  const [trades, setTrades] = useState<Map<string, Trade[]>>(new Map());

  const serviceRef = useRef<MarketDataService | null>(null);

  // 初始化MarketDataService
  useEffect(() => {
    if (!serviceRef.current) {
      serviceRef.current = new MarketDataService(options.url, options.debug ?? false);

      // 监听连接状态
      serviceRef.current.onConnectionStateChange((state) => {
        setConnectionState(state);
      });

      // 自动连接
      if (options.autoConnect !== false) {
        serviceRef.current.connect().catch((error) => {
          console.error('Failed to connect to market data service:', error);
        });
      }

      // 自动订阅symbols
      if (options.symbols && options.symbols.length > 0) {
        options.symbols.forEach((symbol) => {
          subscribeQuoteInternal(symbol);
        });
      }
    }

    return () => {
      if (serviceRef.current) {
        serviceRef.current.disconnect();
        serviceRef.current = null;
      }
    };
  }, [options.url]);

  const subscribeQuoteInternal = (symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.subscribeQuote(symbol, (quote) => {
        setQuotes(((prev: Map<string, Quote>) => {
          const newQuotes = new Map<string, Quote>(prev);
          newQuotes.set(symbol, quote);
          return newQuotes;
        }) as any);
      });
    }
  };

  const subscribeQuote = useCallback((symbol: string) => {
    subscribeQuoteInternal(symbol);
  }, []);

  const unsubscribeQuote = useCallback((symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.unsubscribeQuote(symbol);
      setQuotes(((prev: Map<string, Quote>) => {
        const newQuotes = new Map<string, Quote>(prev);
        newQuotes.delete(symbol);
        return newQuotes;
      }) as any);
    }
  }, []);

  const subscribeTick = useCallback((symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.subscribeTick(symbol, (tick) => {
        setTicks(((prev: Map<string, Tick[]>) => {
          const newTicks = new Map<string, Tick[]>(prev);
          const symbolTicks = (newTicks.get(symbol) ?? []) as Tick[];
          symbolTicks.push(tick);
          // 限制最多100条
          if (symbolTicks.length > 100) {
            symbolTicks.shift();
          }
          newTicks.set(symbol, symbolTicks);
          return newTicks;
        }) as any);
      });
    }
  }, []);

  const unsubscribeTick = useCallback((symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.unsubscribeTick(symbol);
      setTicks(((prev: Map<string, Tick[]>) => {
        const newTicks = new Map<string, Tick[]>(prev);
        newTicks.delete(symbol);
        return newTicks;
      }) as any);
    }
  }, []);

  const subscribeTrade = useCallback((symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.subscribeTrade(symbol, (trade) => {
        setTrades(((prev: Map<string, Trade[]>) => {
          const newTrades = new Map<string, Trade[]>(prev);
          const symbolTrades = (newTrades.get(symbol) ?? []) as Trade[];
          symbolTrades.push(trade);
          // 限制最多100条
          if (symbolTrades.length > 100) {
            symbolTrades.shift();
          }
          newTrades.set(symbol, symbolTrades);
          return newTrades;
        }) as any);
      });
    }
  }, []);

  const unsubscribeTrade = useCallback((symbol: string) => {
    if (serviceRef.current) {
      serviceRef.current.unsubscribeTrade(symbol);
      setTrades(((prev: Map<string, Trade[]>) => {
        const newTrades = new Map<string, Trade[]>(prev);
        newTrades.delete(symbol);
        return newTrades;
      }) as any);
    }
  }, []);

  const getLatestQuote = useCallback((symbol: string): Quote | null => {
    if (serviceRef.current) {
      return serviceRef.current.getLatestQuote(symbol);
    }
    return null;
  }, []);

  const connect = useCallback(async () => {
    if (serviceRef.current) {
      await serviceRef.current.connect();
    }
  }, []);

  const disconnect = useCallback(() => {
    if (serviceRef.current) {
      serviceRef.current.disconnect();
    }
  }, []);

  return {
    connectionState,
    quotes,
    ticks,
    trades,
    subscribeQuote,
    unsubscribeQuote,
    subscribeTick,
    unsubscribeTick,
    subscribeTrade,
    unsubscribeTrade,
    getLatestQuote,
    connect,
    disconnect
  };
}

export default useMarketData;
