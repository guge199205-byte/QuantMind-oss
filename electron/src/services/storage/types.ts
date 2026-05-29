/**
 * 存储服务类型定义
 */

// 数据库配置
export interface DatabaseConfig {
  name: string;
  version: number;
  stores: StoreConfig[];
}

// 存储配置
export interface StoreConfig {
  name: string;
  keyPath?: string | string[];
  autoIncrement?: boolean;
  indexes?: IndexConfig[];
}

// 索引配置
export interface IndexConfig {
  name: string;
  keyPath: string | string[];
  unique?: boolean;
  multiEntry?: boolean;
}

// K线数据
export interface KlineData {
  id?: number;
  symbol: string;
  interval: string;
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closeTime: number;
  quoteVolume: number;
  trades: number;
  takerBuyBaseVolume: number;
  takerBuyQuoteVolume: number;
  createdAt?: number;
}

// 交易记录
export interface TradeRecord {
  id?: number;
  orderId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: string;
  price: number;
  quantity: number;
  quoteQuantity: number;
  commission: number;
  commissionAsset: string;
  timestamp: number;
  isMaker: boolean;
  createdAt?: number;
}

// 订单记录
export interface OrderRecord {
  id?: number;
  orderId: string;
  clientOrderId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: string;
  timeInForce?: string;
  quantity: number;
  price?: number;
  stopPrice?: number;
  status: string;
  executedQty: number;
  cummulativeQuoteQty: number;
  timestamp: number;
  updateTime: number;
  createdAt?: number;
}

// 策略配置
export interface StrategyConfig {
  id?: number;
  name: string;
  type: string;
  symbol: string;
  interval: string;
  parameters: Record<string, unknown>;
  enabled: boolean;
  createdAt: number;
  updatedAt: number;
}

// 用户配置
export interface UserConfig {
  id?: number;
  key: string;
  value: unknown;
  category?: string;
  description?: string;
  updatedAt: number;
}

// 查询选项
export interface QueryOptions {
  limit?: number;
  offset?: number;
  orderBy?: string;
  order?: 'asc' | 'desc';
}

// 范围查询
export interface RangeQuery {
  start: number;
  end: number;
  limit?: number;
}

// 批量操作结果
export interface BatchResult {
  success: number;
  failed: number;
  errors: Error[];
}

// 同步状态
export interface SyncState {
  store: string;
  lastSyncTime: number;
  version: number;
  status: 'idle' | 'syncing' | 'error';
  error?: string;
}

// 缓存条目
export interface CacheEntry<T> {
  key: string;
  value: T;
  timestamp: number;
  ttl: number;
  hits: number;
}

// 缓存统计
export interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  size: number;
  evictions: number;
}

// 存储统计
export interface StorageStats {
  store: string;
  count: number;
  size: number;
  oldestRecord?: number;
  newestRecord?: number;
}
