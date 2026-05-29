/**
 * 交易所API类型定义
 */

// K线数据
export interface Kline {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// 订单簿
export interface OrderBook {
  timestamp: number;
  bids: [number, number][]; // [price, quantity]
  asks: [number, number][];
}

// 成交记录
export interface Trade {
  id: string;
  timestamp: number;
  price: number;
  quantity: number;
  side: 'buy' | 'sell';
}

// 24h行情
export interface Ticker24h {
  symbol: string;
  priceChange: number;
  priceChangePercent: number;
  lastPrice: number;
  highPrice: number;
  lowPrice: number;
  volume: number;
  quoteVolume: number;
}

// 账户余额
export interface Balance {
  asset: string;
  free: number;
  locked: number;
  total: number;
}

// 订单状态
export type OrderStatus =
  | 'NEW'
  | 'PARTIALLY_FILLED'
  | 'FILLED'
  | 'CANCELED'
  | 'REJECTED'
  | 'EXPIRED';

// 订单类型
export type OrderType = 'LIMIT' | 'MARKET' | 'STOP_LOSS' | 'STOP_LOSS_LIMIT';

// 订单方向
export type OrderSide = 'BUY' | 'SELL';

// 订单
export interface Order {
  orderId: string;
  clientOrderId?: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  price?: number;
  quantity: number;
  executedQty: number;
  status: OrderStatus;
  timestamp: number;
  updateTime?: number;
}

// 创建订单参数
export interface CreateOrderParams {
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  stopPrice?: number;
  timeInForce?: 'GTC' | 'IOC' | 'FOK';
  clientOrderId?: string;
}

// 交易所配置
export interface ExchangeConfig {
  apiKey: string;
  apiSecret: string;
  testnet?: boolean;
  timeout?: number;
}

// API响应
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}

// WebSocket订阅类型
export type SubscriptionType =
  | 'kline'
  | 'ticker'
  | 'depth'
  | 'trade'
  | 'account';

// WebSocket消息
export interface WebSocketMessage {
  type: SubscriptionType;
  symbol?: string;
  data: unknown;
  timestamp: number;
}
