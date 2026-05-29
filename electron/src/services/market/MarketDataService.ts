/**
 * 实时行情数据服务 - Week 9 Day 1
 * 提供股票实时行情订阅和数据管理功能
 */

import { WebSocketClient, ConnectionState } from '../websocket/WebSocketClient';

export interface Quote {
  symbol: string;
  name: string;
  price: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  change: number;
  changePercent: number;
  timestamp: number;
  bidPrice?: number;
  askPrice?: number;
  bidVolume?: number;
  askVolume?: number;
}

export interface Tick {
  symbol: string;
  price: number;
  volume: number;
  direction: 'up' | 'down' | 'flat';
  timestamp: number;
}

export interface Trade {
  symbol: string;
  price: number;
  volume: number;
  amount: number;
  type: 'buy' | 'sell';
  timestamp: number;
}

export interface MarketDataSubscription {
  symbol: string;
  type: 'quote' | 'tick' | 'trade';
  callback: (data: any) => void;
}

export type QuoteCallback = (quote: Quote) => void;
export type TickCallback = (tick: Tick) => void;
export type TradeCallback = (trade: Trade) => void;

export class MarketDataService {
  private wsClient: WebSocketClient;
  private quotes = new Map<string, Quote>();
  private ticks = new Map<string, Tick[]>();
  private trades = new Map<string, Trade[]>();
  private subscriptions = new Map<string, MarketDataSubscription>();
  private quoteCallbacks = new Map<string, Set<QuoteCallback>>();
  private tickCallbacks = new Map<string, Set<TickCallback>>();
  private tradeCallbacks = new Map<string, Set<TradeCallback>>();
  private maxTicksPerSymbol = 100;
  private maxTradesPerSymbol = 100;

  constructor(wsUrl: string, debug = false) {
    this.wsClient = new WebSocketClient({
      url: wsUrl,
      reconnect: true,
      reconnectDelay: 1000,
      maxReconnectAttempts: 5,
      heartbeatInterval: 30000,
      debug
    });

    this.setupEventHandlers();
  }

  /**
   * 连接到行情服务器
   */
  async connect(): Promise<void> {
    await this.wsClient.connect();
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.wsClient.disconnect();
    this.clearAllData();
  }

  /**
   * 订阅实时行情
   */
  subscribeQuote(symbol: string, callback: QuoteCallback): string {
    const subscriptionId = `quote_${symbol}_${Date.now()}`;

    if (!this.quoteCallbacks.has(symbol)) {
      this.quoteCallbacks.set(symbol, new Set());
      // 订阅WebSocket频道
      this.wsClient.subscribe(`quote:${symbol}`, (data) => {
        this.handleQuoteData(symbol, data);
      });
    }

    this.quoteCallbacks.get(symbol)!.add(callback);

    // 如果已有缓存数据，立即回调
    const cachedQuote = this.quotes.get(symbol);
    if (cachedQuote) {
      callback(cachedQuote);
    }

    return subscriptionId;
  }

  /**
   * 订阅Tick数据
   */
  subscribeTick(symbol: string, callback: TickCallback): string {
    const subscriptionId = `tick_${symbol}_${Date.now()}`;

    if (!this.tickCallbacks.has(symbol)) {
      this.tickCallbacks.set(symbol, new Set());
      // 订阅WebSocket频道
      this.wsClient.subscribe(`tick:${symbol}`, (data) => {
        this.handleTickData(symbol, data);
      });
    }

    this.tickCallbacks.get(symbol)!.add(callback);

    return subscriptionId;
  }

  /**
   * 订阅成交明细
   */
  subscribeTrade(symbol: string, callback: TradeCallback): string {
    const subscriptionId = `trade_${symbol}_${Date.now()}`;

    if (!this.tradeCallbacks.has(symbol)) {
      this.tradeCallbacks.set(symbol, new Set());
      // 订阅WebSocket频道
      this.wsClient.subscribe(`trade:${symbol}`, (data) => {
        this.handleTradeData(symbol, data);
      });
    }

    this.tradeCallbacks.get(symbol)!.add(callback);

    return subscriptionId;
  }

  /**
   * 取消订阅行情
   */
  unsubscribeQuote(symbol: string, callback?: QuoteCallback): void {
    if (callback) {
      this.quoteCallbacks.get(symbol)?.delete(callback);

      // 如果没有回调了，取消WebSocket订阅
      if (this.quoteCallbacks.get(symbol)?.size === 0) {
        this.wsClient.unsubscribe(`quote:${symbol}`);
        this.quoteCallbacks.delete(symbol);
        this.quotes.delete(symbol);
      }
    } else {
      this.wsClient.unsubscribe(`quote:${symbol}`);
      this.quoteCallbacks.delete(symbol);
      this.quotes.delete(symbol);
    }
  }

  /**
   * 取消订阅Tick
   */
  unsubscribeTick(symbol: string, callback?: TickCallback): void {
    if (callback) {
      this.tickCallbacks.get(symbol)?.delete(callback);

      if (this.tickCallbacks.get(symbol)?.size === 0) {
        this.wsClient.unsubscribe(`tick:${symbol}`);
        this.tickCallbacks.delete(symbol);
        this.ticks.delete(symbol);
      }
    } else {
      this.wsClient.unsubscribe(`tick:${symbol}`);
      this.tickCallbacks.delete(symbol);
      this.ticks.delete(symbol);
    }
  }

  /**
   * 取消订阅成交明细
   */
  unsubscribeTrade(symbol: string, callback?: TradeCallback): void {
    if (callback) {
      this.tradeCallbacks.get(symbol)?.delete(callback);

      if (this.tradeCallbacks.get(symbol)?.size === 0) {
        this.wsClient.unsubscribe(`trade:${symbol}`);
        this.tradeCallbacks.delete(symbol);
        this.trades.delete(symbol);
      }
    } else {
      this.wsClient.unsubscribe(`trade:${symbol}`);
      this.tradeCallbacks.delete(symbol);
      this.trades.delete(symbol);
    }
  }

  /**
   * 获取最新行情
   */
  getLatestQuote(symbol: string): Quote | null {
    return this.quotes.get(symbol) || null;
  }

  /**
   * 获取Tick数据
   */
  getTickData(symbol: string, limit?: number): Tick[] {
    const ticks = this.ticks.get(symbol) || [];
    return limit ? ticks.slice(-limit) : ticks;
  }

  /**
   * 获取成交明细
   */
  getTradeData(symbol: string, limit?: number): Trade[] {
    const trades = this.trades.get(symbol) || [];
    return limit ? trades.slice(-limit) : trades;
  }

  /**
   * 获取连接状态
   */
  getConnectionState(): ConnectionState {
    return this.wsClient.getState();
  }

  /**
   * 获取连接信息
   */
  getConnectionInfo() {
    return this.wsClient.getConnectionInfo();
  }

  /**
   * 监听连接状态变化
   */
  onConnectionStateChange(callback: (state: ConnectionState) => void): void {
    this.wsClient.onStateChange(callback);
  }

  /**
   * 设置事件处理器
   */
  private setupEventHandlers(): void {
    // 连接状态变化
    this.wsClient.onStateChange((state) => {
      if (state === ConnectionState.CONNECTED) {
        this.resubscribeAll();
      }
    });
  }

  /**
   * 处理行情数据
   */
  private handleQuoteData(symbol: string, data: any): void {
    const quote: Quote = {
      symbol,
      name: data.name || symbol,
      price: data.price || 0,
      open: data.open || 0,
      high: data.high || 0,
      low: data.low || 0,
      close: data.close || 0,
      volume: data.volume || 0,
      amount: data.amount || 0,
      change: data.change || 0,
      changePercent: data.changePercent || 0,
      timestamp: data.timestamp || Date.now(),
      bidPrice: data.bidPrice,
      askPrice: data.askPrice,
      bidVolume: data.bidVolume,
      askVolume: data.askVolume
    };

    this.quotes.set(symbol, quote);

    // 触发回调
    const callbacks = this.quoteCallbacks.get(symbol);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(quote);
        } catch (error) {
          console.error('Error in quote callback:', error);
        }
      });
    }
  }

  /**
   * 处理Tick数据
   */
  private handleTickData(symbol: string, data: any): void {
    const tick: Tick = {
      symbol,
      price: data.price || 0,
      volume: data.volume || 0,
      direction: data.direction || 'flat',
      timestamp: data.timestamp || Date.now()
    };

    if (!this.ticks.has(symbol)) {
      this.ticks.set(symbol, []);
    }

    const ticks = this.ticks.get(symbol)!;
    ticks.push(tick);

    // 限制数据量
    if (ticks.length > this.maxTicksPerSymbol) {
      ticks.shift();
    }

    // 触发回调
    const callbacks = this.tickCallbacks.get(symbol);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(tick);
        } catch (error) {
          console.error('Error in tick callback:', error);
        }
      });
    }
  }

  /**
   * 处理成交明细数据
   */
  private handleTradeData(symbol: string, data: any): void {
    const trade: Trade = {
      symbol,
      price: data.price || 0,
      volume: data.volume || 0,
      amount: data.amount || 0,
      type: data.type || 'buy',
      timestamp: data.timestamp || Date.now()
    };

    if (!this.trades.has(symbol)) {
      this.trades.set(symbol, []);
    }

    const trades = this.trades.get(symbol)!;
    trades.push(trade);

    // 限制数据量
    if (trades.length > this.maxTradesPerSymbol) {
      trades.shift();
    }

    // 触发回调
    const callbacks = this.tradeCallbacks.get(symbol);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(trade);
        } catch (error) {
          console.error('Error in trade callback:', error);
        }
      });
    }
  }

  /**
   * 重新订阅所有频道
   */
  private resubscribeAll(): void {
    // 重新订阅所有行情
    this.quoteCallbacks.forEach((_, symbol) => {
      this.wsClient.subscribe(`quote:${symbol}`, (data) => {
        this.handleQuoteData(symbol, data);
      });
    });

    // 重新订阅所有Tick
    this.tickCallbacks.forEach((_, symbol) => {
      this.wsClient.subscribe(`tick:${symbol}`, (data) => {
        this.handleTickData(symbol, data);
      });
    });

    // 重新订阅所有成交明细
    this.tradeCallbacks.forEach((_, symbol) => {
      this.wsClient.subscribe(`trade:${symbol}`, (data) => {
        this.handleTradeData(symbol, data);
      });
    });
  }

  /**
   * 清除所有数据
   */
  private clearAllData(): void {
    this.quotes.clear();
    this.ticks.clear();
    this.trades.clear();
    this.quoteCallbacks.clear();
    this.tickCallbacks.clear();
    this.tradeCallbacks.clear();
  }
}

export default MarketDataService;
